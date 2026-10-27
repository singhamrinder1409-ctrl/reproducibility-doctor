"""Trusted bootstrap source, sent as fixed data to the selected container interpreter.

These snippets must only run IN a preflight container; never on the host.
Project code is not imported, including during metadata/transfer operations.
"""

PROBE = r"""
import errno, fcntl, json, os, platform, resource, socket, struct, sys
from pathlib import Path
interfaces = sorted(name for _, name in socket.if_nameindex())
interface_flags, ipv4_addresses = {}, {}
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as network_socket:
    for name in interfaces:
        request = struct.pack('256s', name.encode())
        flags = fcntl.ioctl(network_socket.fileno(), 0x8913, request)
        interface_flags[name] = struct.unpack('H', flags[16:18])[0]
        try:
            address = fcntl.ioctl(network_socket.fileno(), 0x8915, request)
            ipv4_addresses[name] = socket.inet_ntoa(address[20:24])
        except OSError as error:
            if error.errno != errno.EADDRNOTAVAIL:
                raise
            ipv4_addresses[name] = None
network_details = {
 'interface_flags': interface_flags, 'ipv4_addresses': ipv4_addresses,
 'ipv4_routes': [line.split() for line in Path('/proc/net/route').read_text().splitlines()[1:]
                 if line.strip()],
 'ipv6_routes': [line.split() for line in Path('/proc/net/ipv6_route').read_text().splitlines()
                 if line.strip()],
 'ipv6_addresses': [line.split() for line in Path('/proc/net/if_inet6').read_text().splitlines()
                    if line.strip()]}
def number(name):
    return Path('/sys/fs/cgroup/' + name).read_text().strip()
status = dict(line.split(':', 1) for line in
              Path('/proc/self/status').read_text().splitlines() if ':' in line)
mounts = {}
for line in Path('/proc/self/mountinfo').read_text().splitlines():
    left, right = line.split(' - ', 1)
    fields = left.split()
    mounts[fields[4]] = {'options': fields[5].split(','), 'type': right.split()[0]}
paths = {}
for path in ('/', '/sys', '/sys/fs/cgroup', '/proc/sys',
             '/workspace', '/tmp', '/wheels', '/dev/shm'):
    stat = os.statvfs(path)
    paths[path] = {'read_only': bool(stat.f_flag & os.ST_RDONLY),
                   'bytes': stat.f_blocks * stat.f_frsize, 'mount': mounts.get(path)}
print(json.dumps({'implementation': sys.implementation.name, 'python': list(sys.version_info[:3]),
 'executable': sys.executable, 'version': sys.version, 'machine': platform.machine(),
 'uid': os.getuid(), 'gid': os.getgid(),
 'rlimits': {'core': list(resource.getrlimit(resource.RLIMIT_CORE)),
             'nofile': list(resource.getrlimit(resource.RLIMIT_NOFILE))},
 'status': {k: status[k].strip() for k in ('NoNewPrivs', 'Seccomp', 'CapEff', 'CapPrm', 'CapBnd')},
 'cgroups': {name: number(name) for name in
            ('memory.max', 'memory.swap.max', 'pids.max', 'cpu.max')},
 'network_interfaces': interfaces, 'network_details': network_details,
 'paths': paths,
 'managed_files_writable': [p for p in ('/etc/hosts', '/etc/hostname', '/etc/resolv.conf')
                            if os.access(p, os.W_OK)]}))
"""

RECEIVE = r"""
import hashlib, json, os, tarfile
from pathlib import Path, PurePosixPath
entries = []
total = 0
os.umask(0o022)
with tarfile.open(fileobj=__import__('sys').stdin.buffer, mode='r|') as archive:
    for member in archive:
        parts = PurePosixPath(member.name).parts
        if (not member.isfile() or not parts or parts[0] not in ('workspace', 'wheels')
            or '..' in parts or member.name.startswith('/')):
            raise ValueError('invalid transfer entry')
        total += member.size
        if len(entries) >= 5100 or total > 178 * 1024 * 1024 or member.size > 32 * 1024 * 1024:
            raise ValueError('transfer budget exceeded')
        destination = Path('/') / member.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        reader = archive.extractfile(member)
        with destination.open('xb') as output:
            while chunk := reader.read(65536):
                output.write(chunk)
        destination.chmod(member.mode)
        hasher = hashlib.sha256()
        with destination.open('rb') as source:
            while chunk := source.read(65536):
                hasher.update(chunk)
        entries.append({'path': member.name, 'size': destination.stat().st_size,
                        'mode': member.mode, 'sha256': hasher.hexdigest()})
encoded = json.dumps(sorted(entries, key=lambda e:e['path']), sort_keys=True,
                     separators=(',', ':'), ensure_ascii=True).encode()
print(json.dumps({'digest': hashlib.sha256(encoded).hexdigest(),
                  'files': len(entries), 'bytes': total}))
"""

EXECUTE = r"""
import json, os, sys
from pathlib import Path
job = json.load(sys.stdin)
os.umask(0o022)
cwd = Path('/workspace') / (job['cwd_after'] if job['kind'] == 'change_directory' else job['cwd'])
resolved = cwd.resolve(strict=True)
if not resolved.is_relative_to('/workspace'):
    raise ValueError('working directory escapes workspace')
os.chdir(resolved)
os.environ.clear()
os.environ.update(job['environment'])
if job['kind'] == 'process':
    os.execvpe(job['argv'][0], job['argv'], job['environment'])
"""
