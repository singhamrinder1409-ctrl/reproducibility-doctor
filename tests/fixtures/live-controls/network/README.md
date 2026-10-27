# Run the network and host-isolation probe

This authored development probe attempts IPv4 and IPv6 TCP connections to documentation-only addresses. Both must be denied as unreachable/forbidden. It checks a deliberately created host-only sentinel is absent, checks the host-only environment sentinel was not inherited, checks host home/socket paths are absent, and rejects host-sharing filesystem types. No DNS queries are made; no paid service is used. The harness must set the synthetic host environment sentinel before starting Doctor and preserve the synthetic host file during the run. These checks do not establish protection against kernel vulnerabilities.

```sh
python probe.py
```
