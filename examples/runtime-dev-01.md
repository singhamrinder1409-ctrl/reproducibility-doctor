> **Genuine approved reserved-corpus run.** Expected failures are validation outcomes, not claims of general setup accuracy.

# Reproducibility Doctor — run report

Experimental execution; live validation: pending

This report interprets a local record; it does not authenticate evidence or certify safety.

Snapshot digest: 3c27a5478f5948e849dc5fad2638c1bfa28088ac9a9153abf80650ef98cf611a

Plan digest: d13f485b66f52137ddf8ea8692cd2679460dc80e22a34275127b9f5effe02135

Input execution record SHA-256 (canonical JSON): a3e878df8d50031d8483997d8195d5ea7a4d5e91f3a9c67483bcb586b980c263

Cleanup: {&#x27;status&#x27;: &#x27;removed&#x27;, &#x27;container&#95;name&#x27;: &#x27;reprodoctor-5b9f0843375b43ae9b23243148a149fb&#x27;}

Runner error: None

## Recorded steps

### instruction-0001 — passed

Source: {&#x27;id&#x27;: &#x27;instruction-0001&#x27;, &#x27;order&#x27;: 1, &#x27;block&#95;id&#x27;: &#x27;block-0001&#x27;, &#x27;path&#x27;: &#x27;README.md&#x27;, &#x27;start&#95;line&#x27;: 3, &#x27;end&#95;line&#x27;: 3, &#x27;raw&#95;text&#x27;: &#x27;python app.py&#92;n&#x27;, &#x27;candidate&#95;text&#x27;: &#x27;python app.py&#x27;, &#x27;phase&#x27;: &#x27;launch&#x27;, &#x27;command&#95;phase&#x27;: &#x27;launch&#x27;, &#x27;heading&#95;phase&#x27;: &#x27;launch&#x27;, &#x27;heading&#95;context&#x27;: &#91;{&#x27;level&#x27;: 1, &#x27;text&#x27;: &#x27;Run&#x27;, &#x27;line&#x27;: 1}&#93;, &#x27;classification&#x27;: &#x27;command&#95;candidate&#x27;, &#x27;ambiguity&#95;reasons&#x27;: &#91;&#93;, &#x27;requires&#95;review&#x27;: True}

Effective command/state: {&#x27;kind&#x27;: &#x27;process&#x27;, &#x27;argv&#x27;: &#91;&#x27;python&#x27;, &#x27;app.py&#x27;&#93;, &#x27;cwd&#x27;: &#x27;.&#x27;, &#x27;environment&#x27;: {&#x27;PATH&#x27;: &#x27;/usr/local/bin:/usr/bin:/bin&#x27;, &#x27;HOME&#x27;: &#x27;/tmp&#x27;, &#x27;PYTHONDONTWRITEBYTECODE&#x27;: &#x27;1&#x27;, &#x27;PYTHONNOUSERSITE&#x27;: &#x27;1&#x27;, &#x27;PYTHONPATH&#x27;: &#x27;/workspace/.doctor-packages&#x27;, &#x27;PIP&#95;CONFIG&#95;FILE&#x27;: &#x27;/dev/null&#x27;, &#x27;PIP&#95;NO&#95;INDEX&#x27;: &#x27;1&#x27;, &#x27;PIP&#95;DISABLE&#95;PIP&#95;VERSION&#95;CHECK&#x27;: &#x27;1&#x27;, &#x27;PIP&#95;NO&#95;INPUT&#x27;: &#x27;1&#x27;}, &#x27;transformations&#x27;: &#91;&#93;, &#x27;network&#95;assessment&#x27;: &#x27;Program network requirements are unknown; network is denied.&#x27;, &#x27;cwd&#95;after&#x27;: &#x27;.&#x27;, &#x27;environment&#95;after&#x27;: {&#x27;PATH&#x27;: &#x27;/usr/local/bin:/usr/bin:/bin&#x27;, &#x27;HOME&#x27;: &#x27;/tmp&#x27;, &#x27;PYTHONDONTWRITEBYTECODE&#x27;: &#x27;1&#x27;, &#x27;PYTHONNOUSERSITE&#x27;: &#x27;1&#x27;, &#x27;PYTHONPATH&#x27;: &#x27;/workspace/.doctor-packages&#x27;, &#x27;PIP&#95;CONFIG&#95;FILE&#x27;: &#x27;/dev/null&#x27;, &#x27;PIP&#95;NO&#95;INDEX&#x27;: &#x27;1&#x27;, &#x27;PIP&#95;DISABLE&#95;PIP&#95;VERSION&#95;CHECK&#x27;: &#x27;1&#x27;, &#x27;PIP&#95;NO&#95;INPUT&#x27;: &#x27;1&#x27;}}

Exit code/source: &#91;0, &#x27;docker&#95;exec&#95;cli&#x27;&#93;

Elapsed seconds: 0.121506

stdout (bounded): {&#x27;text&#x27;: &#x27;ok&#92;n&#x27;, &#x27;total&#95;bytes&#x27;: 3, &#x27;captured&#95;bytes&#x27;: 3, &#x27;truncated&#x27;: False, &#x27;sha256&#95;observed&#95;stream&#x27;: &#x27;dc51b8c96c2d745df3bd5590d990230a482fd247123599548e0632fdbf97fc22&#x27;}

stderr (bounded): {&#x27;text&#x27;: &#x27;&#x27;, &#x27;total&#95;bytes&#x27;: 0, &#x27;captured&#95;bytes&#x27;: 0, &#x27;truncated&#x27;: False, &#x27;sha256&#95;observed&#95;stream&#x27;: &#x27;e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855&#x27;}

Not reached: &#91;&#93;

## Environment and evidence

Approved settings: {&#x27;image&#x27;: &#x27;python@sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f&#x27;, &#x27;platform&#x27;: &#x27;linux/arm64&#x27;, &#x27;expected&#95;python&#95;series&#x27;: &#x27;3.12&#x27;, &#x27;network&#x27;: &#x27;none&#x27;, &#x27;ports&#x27;: &#91;&#93;, &#x27;host&#95;mounts&#x27;: &#91;&#93;, &#x27;privileged&#x27;: False, &#x27;user&#x27;: &#x27;65532:65532&#x27;, &#x27;cap&#95;drop&#x27;: &#91;&#x27;ALL&#x27;&#93;, &#x27;no&#95;new&#95;privileges&#x27;: True, &#x27;seccomp&#x27;: &#x27;runtime&#95;default&#95;required&#x27;, &#x27;root&#95;filesystem&#x27;: &#x27;read&#95;only&#x27;, &#x27;entrypoint&#x27;: &#x27;overridden&#95;no&#95;image&#95;startup&#95;command&#x27;, &#x27;healthcheck&#x27;: &#x27;disabled&#x27;, &#x27;runtime&#95;log&#95;driver&#x27;: &#x27;none&#x27;, &#x27;runtime&#95;namespaces&#x27;: {&#x27;ipc&#x27;: &#x27;private&#x27;, &#x27;cgroup&#x27;: &#x27;private&#x27;, &#x27;pid&#x27;: &#x27;private&#x27;}, &#x27;runtime&#95;support&#x27;: &#x27;experimental&#95;local&#95;Docker&#95;Linux&#95;cgroup&#95;v2&#95;builtin&#95;seccomp&#x27;, &#x27;environment&#x27;: {&#x27;PATH&#x27;: &#x27;/usr/local/bin:/usr/bin:/bin&#x27;, &#x27;HOME&#x27;: &#x27;/tmp&#x27;, &#x27;PYTHONDONTWRITEBYTECODE&#x27;: &#x27;1&#x27;, &#x27;PYTHONNOUSERSITE&#x27;: &#x27;1&#x27;, &#x27;PYTHONPATH&#x27;: &#x27;/workspace/.doctor-packages&#x27;, &#x27;PIP&#95;CONFIG&#95;FILE&#x27;: &#x27;/dev/null&#x27;, &#x27;PIP&#95;NO&#95;INDEX&#x27;: &#x27;1&#x27;, &#x27;PIP&#95;DISABLE&#95;PIP&#95;VERSION&#95;CHECK&#x27;: &#x27;1&#x27;, &#x27;PIP&#95;NO&#95;INPUT&#x27;: &#x27;1&#x27;}, &#x27;inherit&#95;host&#95;environment&#x27;: False, &#x27;image&#95;environment&#x27;: &#x27;must&#95;clear&#95;before&#95;project&#95;steps&#x27;, &#x27;source&#95;transfer&#x27;: &#x27;copy&#95;only&#95;verified&#95;snapshot&#95;no&#95;git&#95;metadata&#x27;, &#x27;source&#95;copy&#95;permissions&#x27;: &#x27;user&#95;writable&#95;0644&#95;or&#95;0755&#95;matching&#95;tracked&#95;executable&#95;bit&#x27;, &#x27;project&#95;umask&#x27;: &#x27;0022&#x27;, &#x27;artifact&#95;transfer&#x27;: &#x27;copy&#95;only&#95;verified&#95;wheels&#95;no&#95;host&#95;mounts&#x27;, &#x27;writable&#95;tmpfs&#x27;: {&#x27;/workspace&#x27;: 268435456, &#x27;/tmp&#x27;: 67108864, &#x27;/wheels&#x27;: 134217728}, &#x27;shared&#95;memory&#95;bytes&#x27;: 16777216, &#x27;limits&#x27;: {&#x27;cpus&#x27;: 1, &#x27;memory&#95;bytes&#x27;: 1073741824, &#x27;extra&#95;swap&#95;bytes&#x27;: 0, &#x27;pids&#x27;: 128, &#x27;step&#95;seconds&#x27;: 120, &#x27;run&#95;seconds&#x27;: 600, &#x27;log&#95;bytes&#95;per&#95;stream&#95;per&#95;step&#x27;: 1048576, &#x27;run&#95;log&#95;bytes&#x27;: 4194304, &#x27;core&#95;bytes&#x27;: 0, &#x27;open&#95;files&#x27;: 256}, &#x27;cleanup&#x27;: &#x27;remove&#95;container&#95;and&#95;temporary&#95;data&#95;on&#95;exit&#95;or&#95;reconcile&#95;after&#95;interruption&#x27;, &#x27;preflight&#95;required&#x27;: &#91;&#x27;verify&#95;local&#95;image&#95;digest&#95;and&#95;platform&#x27;, &#x27;verify&#95;CPython&#95;3.12&#x27;, &#x27;reject&#95;image&#95;declared&#95;volumes&#x27;, &#x27;verify&#95;all&#95;resource&#95;controls&#x27;, &#x27;clear&#95;image&#95;entrypoint&#95;and&#95;environment&#x27;, &#x27;verify&#95;no&#95;sensitive&#95;mounts&#x27;&#93;}

Observed preflight: {&#x27;server&#95;observed&#x27;: {&#x27;ServerVersion&#x27;: &#x27;29.9.2&#x27;, &#x27;OSType&#x27;: &#x27;linux&#x27;, &#x27;CgroupVersion&#x27;: &#x27;2&#x27;, &#x27;SecurityOptions&#x27;: &#91;&#x27;name=seccomp,profile=builtin&#x27;, &#x27;name=cgroupns&#x27;&#93;}, &#x27;server&#x27;: {&#x27;ServerVersion&#x27;: &#x27;29.9.2&#x27;, &#x27;OSType&#x27;: &#x27;linux&#x27;, &#x27;CgroupVersion&#x27;: &#x27;2&#x27;, &#x27;SecurityOptions&#x27;: &#91;&#x27;name=seccomp,profile=builtin&#x27;, &#x27;name=cgroupns&#x27;&#93;}, &#x27;image&#x27;: {&#x27;id&#x27;: &#x27;sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f&#x27;, &#x27;repo&#95;digest&#x27;: &#x27;sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f&#x27;, &#x27;platform&#x27;: &#x27;linux/arm64&#x27;, &#x27;image&#95;environment&#95;keys&#95;cleared&#x27;: &#91;&#x27;GPG&#95;KEY&#x27;, &#x27;LANG&#x27;, &#x27;PATH&#x27;, &#x27;PYTHON&#95;SHA256&#x27;, &#x27;PYTHON&#95;VERSION&#x27;&#93;}, &#x27;container&#95;observed&#x27;: {&#x27;image&#95;id&#x27;: &#x27;sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f&#x27;, &#x27;host&#95;config&#x27;: {&#x27;NetworkMode&#x27;: &#x27;none&#x27;, &#x27;ReadonlyRootfs&#x27;: True, &#x27;Memory&#x27;: 1073741824, &#x27;MemorySwap&#x27;: 1073741824, &#x27;PidsLimit&#x27;: 128, &#x27;NanoCpus&#x27;: 1000000000, &#x27;SecurityOpt&#x27;: &#91;&#x27;no-new-privileges=true&#x27;&#93;, &#x27;Privileged&#x27;: False, &#x27;Binds&#x27;: None, &#x27;Devices&#x27;: &#91;&#93;, &#x27;Tmpfs&#x27;: {&#x27;/tmp&#x27;: &#x27;rw,nosuid,nodev,size=67108864,uid=65532,gid=65532,mode=0700&#x27;, &#x27;/wheels&#x27;: &#x27;rw,nosuid,nodev,size=134217728,uid=65532,gid=65532,mode=0700&#x27;, &#x27;/workspace&#x27;: &#x27;rw,nosuid,nodev,size=268435456,uid=65532,gid=65532,mode=0700&#x27;}}}, &#x27;container&#x27;: {&#x27;image&#95;id&#x27;: &#x27;sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f&#x27;, &#x27;host&#95;config&#95;verified&#x27;: {&#x27;NetworkMode&#x27;: &#x27;none&#x27;, &#x27;IpcMode&#x27;: &#x27;private&#x27;, &#x27;CgroupnsMode&#x27;: &#x27;private&#x27;, &#x27;ReadonlyRootfs&#x27;: True, &#x27;Privileged&#x27;: False, &#x27;NanoCpus&#x27;: 1000000000, &#x27;Memory&#x27;: 1073741824, &#x27;MemorySwap&#x27;: 1073741824, &#x27;PidsLimit&#x27;: 128, &#x27;ShmSize&#x27;: 16777216, &#x27;CapDrop&#x27;: &#91;&#x27;ALL&#x27;&#93;, &#x27;Init&#x27;: True}, &#x27;environment&#95;keys&#x27;: &#91;&#x27;GPG&#95;KEY&#x27;, &#x27;HOME&#x27;, &#x27;LANG&#x27;, &#x27;PATH&#x27;, &#x27;PIP&#95;CONFIG&#95;FILE&#x27;, &#x27;PIP&#95;DISABLE&#95;PIP&#95;VERSION&#95;CHECK&#x27;, &#x27;PIP&#95;NO&#95;INDEX&#x27;, &#x27;PIP&#95;NO&#95;INPUT&#x27;, &#x27;PYTHONDONTWRITEBYTECODE&#x27;, &#x27;PYTHONNOUSERSITE&#x27;, &#x27;PYTHONPATH&#x27;, &#x27;PYTHON&#95;SHA256&#x27;, &#x27;PYTHON&#95;VERSION&#x27;&#93;, &#x27;healthcheck&#95;disabled&#x27;: True}, &#x27;kernel&#x27;: {&#x27;implementation&#x27;: &#x27;cpython&#x27;, &#x27;python&#x27;: &#91;3, 12, 16&#93;, &#x27;executable&#x27;: &#x27;/usr/local/bin/python&#x27;, &#x27;version&#x27;: &#x27;3.12.16 (main, Oct 26 2026, 22:56:41) &#91;GCC 14.2.0&#93;&#x27;, &#x27;machine&#x27;: &#x27;aarch64&#x27;, &#x27;uid&#x27;: 65532, &#x27;gid&#x27;: 65532, &#x27;rlimits&#x27;: {&#x27;core&#x27;: &#91;0, 0&#93;, &#x27;nofile&#x27;: &#91;256, 256&#93;}, &#x27;status&#x27;: {&#x27;NoNewPrivs&#x27;: &#x27;1&#x27;, &#x27;Seccomp&#x27;: &#x27;2&#x27;, &#x27;CapEff&#x27;: &#x27;0000000000000000&#x27;, &#x27;CapPrm&#x27;: &#x27;0000000000000000&#x27;, &#x27;CapBnd&#x27;: &#x27;0000000000000000&#x27;}, &#x27;cgroups&#x27;: {&#x27;memory.max&#x27;: &#x27;1073741824&#x27;, &#x27;memory.swap.max&#x27;: &#x27;0&#x27;, &#x27;pids.max&#x27;: &#x27;128&#x27;, &#x27;cpu.max&#x27;: &#x27;100000 100000&#x27;}, &#x27;network&#95;interfaces&#x27;: &#91;&#x27;erspan0&#x27;, &#x27;gre0&#x27;, &#x27;gretap0&#x27;, &#x27;ip6&#95;vti0&#x27;, &#x27;ip6gre0&#x27;, &#x27;ip6tnl0&#x27;, &#x27;ip&#95;vti0&#x27;, &#x27;lo&#x27;, &#x27;sit0&#x27;, &#x27;tunl0&#x27;&#93;, &#x27;network&#95;details&#x27;: {&#x27;interface&#95;flags&#x27;: {&#x27;erspan0&#x27;: 4098, &#x27;gre0&#x27;: 128, &#x27;gretap0&#x27;: 4098, &#x27;ip6&#95;vti0&#x27;: 128, &#x27;ip6gre0&#x27;: 128, &#x27;ip6tnl0&#x27;: 128, &#x27;ip&#95;vti0&#x27;: 128, &#x27;lo&#x27;: 73, &#x27;sit0&#x27;: 128, &#x27;tunl0&#x27;: 128}, &#x27;ipv4&#95;addresses&#x27;: {&#x27;erspan0&#x27;: None, &#x27;gre0&#x27;: None, &#x27;gretap0&#x27;: None, &#x27;ip6&#95;vti0&#x27;: None, &#x27;ip6gre0&#x27;: None, &#x27;ip6tnl0&#x27;: None, &#x27;ip&#95;vti0&#x27;: None, &#x27;lo&#x27;: &#x27;127.0.0.1&#x27;, &#x27;sit0&#x27;: None, &#x27;tunl0&#x27;: None}, &#x27;ipv4&#95;routes&#x27;: &#91;&#93;, &#x27;ipv6&#95;routes&#x27;: &#91;&#91;&#x27;00000000000000000000000000000000&#x27;, &#x27;00&#x27;, &#x27;00000000000000000000000000000000&#x27;, &#x27;00&#x27;, &#x27;00000000000000000000000000000000&#x27;, &#x27;ffffffff&#x27;, &#x27;00000001&#x27;, &#x27;00000000&#x27;, &#x27;00200200&#x27;, &#x27;lo&#x27;&#93;, &#91;&#x27;00000000000000000000000000000001&#x27;, &#x27;80&#x27;, &#x27;00000000000000000000000000000000&#x27;, &#x27;00&#x27;, &#x27;00000000000000000000000000000000&#x27;, &#x27;00000000&#x27;, &#x27;00000002&#x27;, &#x27;00000000&#x27;, &#x27;80200001&#x27;, &#x27;lo&#x27;&#93;, &#91;&#x27;00000000000000000000000000000000&#x27;, &#x27;00&#x27;, &#x27;00000000000000000000000000000000&#x27;, &#x27;00&#x27;, &#x27;00000000000000000000000000000000&#x27;, &#x27;ffffffff&#x27;, &#x27;00000001&#x27;, &#x27;00000000&#x27;, &#x27;00200200&#x27;, &#x27;lo&#x27;&#93;&#93;, &#x27;ipv6&#95;addresses&#x27;: &#91;&#91;&#x27;00000000000000000000000000000001&#x27;, &#x27;01&#x27;, &#x27;80&#x27;, &#x27;10&#x27;, &#x27;80&#x27;, &#x27;lo&#x27;&#93;&#93;}, &#x27;paths&#x27;: {&#x27;/&#x27;: {&#x27;read&#95;only&#x27;: True, &#x27;bytes&#x27;: 240120725504, &#x27;mount&#x27;: {&#x27;options&#x27;: &#91;&#x27;ro&#x27;, &#x27;relatime&#x27;&#93;, &#x27;type&#x27;: &#x27;overlay&#x27;}}, &#x27;/sys&#x27;: {&#x27;read&#95;only&#x27;: True, &#x27;bytes&#x27;: 0, &#x27;mount&#x27;: {&#x27;options&#x27;: &#91;&#x27;ro&#x27;, &#x27;nosuid&#x27;, &#x27;nodev&#x27;, &#x27;noexec&#x27;, &#x27;relatime&#x27;&#93;, &#x27;type&#x27;: &#x27;sysfs&#x27;}}, &#x27;/sys/fs/cgroup&#x27;: {&#x27;read&#95;only&#x27;: True, &#x27;bytes&#x27;: 0, &#x27;mount&#x27;: {&#x27;options&#x27;: &#91;&#x27;ro&#x27;, &#x27;nosuid&#x27;, &#x27;nodev&#x27;, &#x27;noexec&#x27;, &#x27;relatime&#x27;&#93;, &#x27;type&#x27;: &#x27;cgroup2&#x27;}}, &#x27;/proc/sys&#x27;: {&#x27;read&#95;only&#x27;: True, &#x27;bytes&#x27;: 0, &#x27;mount&#x27;: {&#x27;options&#x27;: &#91;&#x27;ro&#x27;, &#x27;nosuid&#x27;, &#x27;nodev&#x27;, &#x27;noexec&#x27;, &#x27;relatime&#x27;&#93;, &#x27;type&#x27;: &#x27;proc&#x27;}}, &#x27;/workspace&#x27;: {&#x27;read&#95;only&#x27;: False, &#x27;bytes&#x27;: 268435456, &#x27;mount&#x27;: {&#x27;options&#x27;: &#91;&#x27;rw&#x27;, &#x27;nosuid&#x27;, &#x27;nodev&#x27;, &#x27;noexec&#x27;, &#x27;relatime&#x27;&#93;, &#x27;type&#x27;: &#x27;tmpfs&#x27;}}, &#x27;/tmp&#x27;: {&#x27;read&#95;only&#x27;: False, &#x27;bytes&#x27;: 67108864, &#x27;mount&#x27;: {&#x27;options&#x27;: &#91;&#x27;rw&#x27;, &#x27;nosuid&#x27;, &#x27;nodev&#x27;, &#x27;noexec&#x27;, &#x27;relatime&#x27;&#93;, &#x27;type&#x27;: &#x27;tmpfs&#x27;}}, &#x27;/wheels&#x27;: {&#x27;read&#95;only&#x27;: False, &#x27;bytes&#x27;: 134217728, &#x27;mount&#x27;: {&#x27;options&#x27;: &#91;&#x27;rw&#x27;, &#x27;nosuid&#x27;, &#x27;nodev&#x27;, &#x27;noexec&#x27;, &#x27;relatime&#x27;&#93;, &#x27;type&#x27;: &#x27;tmpfs&#x27;}}, &#x27;/dev/shm&#x27;: {&#x27;read&#95;only&#x27;: False, &#x27;bytes&#x27;: 16777216, &#x27;mount&#x27;: {&#x27;options&#x27;: &#91;&#x27;rw&#x27;, &#x27;nosuid&#x27;, &#x27;nodev&#x27;, &#x27;noexec&#x27;, &#x27;relatime&#x27;&#93;, &#x27;type&#x27;: &#x27;tmpfs&#x27;}}}, &#x27;managed&#95;files&#95;writable&#x27;: &#91;&#93;}, &#x27;transfer&#x27;: {&#x27;digest&#x27;: &#x27;30a93317616d31fa7f005803031ebf121c2e387ef15ae597d85d45dce73485bc&#x27;, &#x27;files&#x27;: 3, &#x27;bytes&#x27;: 139}, &#x27;status&#x27;: &#x27;verified&#95;for&#95;this&#95;run&#x27;}

Artifacts: {&#x27;files&#x27;: &#91;&#93;, &#x27;content&#95;digest&#x27;: &#x27;4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945&#x27;, &#x27;total&#95;bytes&#x27;: 0, &#x27;container&#95;directory&#x27;: &#x27;/wheels&#x27;, &#x27;validation&#x27;: &#x27;hashes&#95;only&#95;not&#95;wheel&#95;validity&#x27;}

Engine: {&#x27;tool&#95;version&#x27;: &#x27;0.1.0.dev0&#x27;, &#x27;contract&#95;version&#x27;: 1, &#x27;code&#95;digest&#x27;: &#x27;490b871939972a1f75b8e37f4721246d7c1c24168d3eb1de3ed9b85c9f173452&#x27;, &#x27;markdown&#95;it&#95;version&#x27;: &#x27;4.2.0&#x27;, &#x27;mdurl&#95;version&#x27;: &#x27;0.1.2&#x27;}

# Reproducibility Doctor — failure diagnosis

Execution status: completed

Live validation: pending

Commit: 0f4b3461e1127174b1efd595b34d8a1ec926d5c2

No failure findings from the recorded fields. This is not a reproducibility verdict.

## Limits

- This interprets an editable local execution record; it does not authenticate the record or rerun commands.
- Logs are untrusted and may be forged, incomplete or truncated. Pattern matches are suggestions only.
- No match means unknown cause. Successful commands are not proof of reproducibility or application correctness.
- Docker CLI and program exit codes can be ambiguous; no signal or exact root cause is inferred.

## Reproduction steps

1. Obtain the recorded commit and verify its snapshot content digest.
2. Use the recorded Doctor engine, platform, digest-pinned image and offline artifact hashes.
3. Rebuild the plan with the same explicit review decisions and inspect every command/settings.
4. Approve the new plan interactively before any execution; supply the explicit local Docker socket.
5. Run only if the runtime passes the recorded policy. Compare statuses, logs and cleanup evidence.

# Reproducibility Doctor — static inspection

Execution: **not run**. This report contains static observations, not a setup verdict.

Commit: 0f4b3461e1127174b1efd595b34d8a1ec926d5c2
Snapshot digest: 3c27a5478f5948e849dc5fad2638c1bfa28088ac9a9153abf80650ef98cf611a
Static target Python: 3.12.16
Checker environment: {&#x27;python&#x27;: &#x27;3.14.5&#x27;, &#x27;dependencies&#x27;: {&#x27;packaging&#x27;: &#x27;26.3&#x27;, &#x27;markdown-it-py&#x27;: &#x27;4.2.0&#x27;, &#x27;mdurl&#x27;: &#x27;0.1.2&#x27;}}

Status counts: pass=4, unknown=3

## static-0001: dependencies — pass

Observed: Recognized manifest files are present.

Suggested next action: Review the dependency workflow; manifest presence is not an installation result.

Limit: Manifest checks do not prove dependency completeness or availability.

Evidence: pyproject.toml; SHA-256: ed6a2b294394ca5324bca85096864e4c843c2faf9353e5f0f5550efb7d3bdc19

## static-0002: dependencies — pass

Observed: Explicit project dependency strings parse successfully.

Suggested next action: Verify completeness and installation in an approved environment.

Limit: Manifest checks do not prove dependency completeness or availability.

Evidence: pyproject.toml; SHA-256: ed6a2b294394ca5324bca85096864e4c843c2faf9353e5f0f5550efb7d3bdc19

## static-0003: python — pass

Observed: Static target Python 3.12.16 satisfies declaration &gt;=3.12.

Suggested next action: Choose an allowed exact runtime; exclusion does not mean the project is broken.

Limit: Only explicit declarations are compared; the static target has not run.

Evidence: pyproject.toml; SHA-256: ed6a2b294394ca5324bca85096864e4c843c2faf9353e5f0f5550efb7d3bdc19

## static-0004: consistency — unknown

Observed: Fewer than two supported Python declarations are available to compare.

Suggested next action: Review documentation and configuration together.

Limit: Explicit declaration overlap does not prove runtime compatibility.

Evidence: snapshot inventory / limited check coverage.

## static-0005: references — pass

Observed: Literal input file &#x27;app.py&#x27; is present in the snapshot.

Suggested next action: Check spelling, working directory and generation before calling this a defect.

Limit: Only literal inputs are checked; missing files may be generated or external.

Evidence: README.md:3; SHA-256: 8e599fb1c318ee37bad7972635d2d08d84b62b2200d255895e910eedadd905e3

Evidence: app.py; SHA-256: 3a66aebdedbad3cf107d24e72a07d4b735819b1cf4020fdd922f63c064708172

## static-0006: references — unknown

Observed: Inspected 1 supported inputs; ambiguous commands and prose paths were not resolved.

Suggested next action: Review extraction flags, shell state and generated files manually.

Limit: Only literal inputs are checked; missing files may be generated or external.

Evidence: snapshot inventory / limited check coverage.

## static-0007: environment — unknown

Observed: Variable requiredness and dynamically constructed names are not established.

Suggested next action: Review aliases, defaults and external configuration before diagnosing a defect.

Limit: Name matching does not establish requiredness or resolve dynamic access.

Evidence: snapshot inventory / limited check coverage.

## Reproduce this inspection

1. Obtain the same committed source and verify the recorded snapshot digest.
2. Use the recorded Doctor version and dependency versions.
3. Run reprodoctor check SNAPSHOT --python-version 3.12.16 --format markdown.
4. Review findings alongside the source. No project commands have run.

Doctor version: 0.1.0.dev0

## Coverage and limitations

- Manifest checks do not prove dependency completeness or availability.
- Only explicit declarations are compared; the static target has not run.
- Only literal inputs are checked; missing files may be generated or external.
- Name matching does not establish requiredness or resolve dynamic access.
- Explicit declaration overlap does not prove runtime compatibility.
- Static passes are not setup runs; no index or build backend was queried.

