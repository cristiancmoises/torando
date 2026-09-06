# Torando on FreeBSD

The `torando.sh` and `toroff.sh` commands in this repository use Linux
iptables. They do not run on FreeBSD.

**[Torando-Gui](https://github.com/cristiancmoises/torando-gui) is the GUI for
Torando.** Its FreeBSD backend is available in beta and uses SOCKS with a
per-user pf firewall. See its [platform notes](https://github.com/cristiancmoises/torando-gui/blob/main/docs/USAGE.md#platform-notes)
for installation, DNS setup and the limitations of that backend.

If you only need a Tor connection for a specific application, you can configure
SOCKS directly. This does not install a system-wide firewall or protect apps
that ignore the proxy.

## Set up Tor

Install Tor as root:

```sh
pkg install tor
```

Edit `/usr/local/etc/tor/torrc` and configure a local SOCKS listener:

```text
SocksPort 127.0.0.1:9050
```

Check the configuration, enable the service and start it:

```sh
tor --verify-config -f /usr/local/etc/tor/torrc
sysrc tor_enable="YES"
service tor start
```

If Tor is already running, restart the service after changing its configuration.
Wait for it to finish bootstrapping, then run this as your normal user (install
`curl` with `pkg install curl` if needed):

```sh
curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip
```

`--socks5-hostname` asks the proxy to resolve the destination name. A response
containing `"IsTor": true` verifies this request. For other applications, set
SOCKS5 to `127.0.0.1:9050` and enable proxy-side DNS if supported.

## About the earlier pf instructions

The previous version of this page combined `set skip on lo` with redirection
on `lo0`. That recipe did not establish the claimed transparent routing. It
also configured a DNS listener on port 5353 while pointing ordinary DNS clients
at port 53, and used Linux filesystem commands on FreeBSD.

Those instructions have been removed. The SOCKS setup above leaves your
resolver and pf configuration alone. If you used the old recipe, restore your
saved configuration and review your existing rules before reloading pf. Avoid
replacing a working firewall with a generic example.

For the underlying configuration details, consult the
[Tor manual](https://man.freebsd.org/cgi/man.cgi?manpath=freebsd-ports&query=tor&sektion=1)
and the [FreeBSD firewall handbook](https://docs.freebsd.org/en/books/handbook/firewalls/).
