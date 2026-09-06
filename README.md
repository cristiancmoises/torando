# Torando

Torando routes one Linux user's IPv4 TCP connections through Tor and blocks
other outgoing traffic for that user. It is a small command-line tool for
people who already run Tor and want to turn routing on and off without editing
firewall commands by hand.

**[Torando-Gui](https://github.com/cristiancmoises/torando-gui) is the GUI for
Torando.** It provides a desktop interface, connection status, exit checks and
settings. It installs its own daemon; you do not need to install these scripts
first. Use one controller at a time for a given user.

[Português](LEIA-ME.md) · [FreeBSD](freebsd.md) · [Security](SECURITY.md)

## What's new in 2.0.0

You can now select a user with `--user`, check the current rules with `--status`,
and run enable or disable more than once without accumulating rules. Torando
uses its own chains, preserves unrelated firewall rules, and blocks outgoing
IPv6 for the selected user. If a firewall change fails after a blocking guard
has been installed, the guard stays in place until you recover or disable it.

This replaces the old scripts containing `USERAQUI`. Read the upgrade notes
below before switching an existing setup.

## Before you start

You need Linux, Bash, `iptables`, `ip6tables` unless IPv6 is disabled at kernel boot,
`flock` from util-linux, `pgrep` from procps, and a Tor service running under a separate account.
Run the scripts through `sudo` from your normal login. Root and known Tor
service accounts cannot be selected as the target.

On Debian or Ubuntu, install the packages with:

```sh
sudo apt update
sudo apt install tor iptables util-linux procps
```

Install the equivalent packages with your distribution's package manager on
other systems. These scripts do not install or start Tor for you.

## Configure Tor

Edit your service's `torrc` (usually `/etc/tor/torrc`) and add or update these
settings once:

```text
SocksPort 127.0.0.1:9050
TransPort 127.0.0.1:9040
DNSPort 127.0.0.1:5353
VirtualAddrNetworkIPv4 10.192.0.0/10
AutomapHostsOnResolve 1
```

Keep the listeners on loopback. Check the configuration, then restart Tor using
your distribution's service manager. For a typical systemd installation:

```sh
sudo tor --verify-config -f /etc/tor/torrc
sudo systemctl restart tor
```

Tor's DNS listener handles UDP A, AAAA and PTR queries. The
[Tor manual](https://man.freebsd.org/cgi/man.cgi?manpath=freebsd-ports&query=tor&sektion=1)
explains the listener and virtual-address options.

Torando redirects the selected user's IPv4 UDP queries on port 53 to the local
Tor DNS listener, including queries addressed to a loopback DNS stub. It does
not edit `/etc/resolv.conf` or make files immutable. DNS requests delegated over
a Unix socket to a resolver running as another user are outside these per-user
rules; check how your system resolves names before relying on this setup.

## Connect, check and disconnect

Close applications with existing network connections before enabling. Existing
UDP DNS sockets can retain a conntrack mapping to your old resolver, including a
loopback stub. Reopen the applications after the rules are installed.

```sh
git clone https://github.com/cristiancmoises/torando.git
cd torando
./torando.sh --version
sudo ./torando.sh
sudo ./torando.sh --status
```

Without `--user`, Torando selects the user who invoked `sudo`. From a root
shell, choose the target explicitly:

```sh
sudo ./torando.sh --user alice
sudo ./torando.sh --status --user alice
sudo ./toroff.sh --user alice
```

To disconnect your own login:

```sh
sudo ./toroff.sh
```

If your Tor listeners use different ports, pass matching values when enabling:

```sh
sudo ./torando.sh --trans-port 9041 --dns-port 5354
```

Run `./torando.sh --help` for the available options. Status checks inspect the
firewall rules; they do not prove that Tor has bootstrapped or that a remote
request used Tor. Exit codes are `0` for enabled, `3` for disabled, and `2` for
an incomplete or modified ruleset.

From a terminal owned by the selected user, open a fresh connection to check
routing:

```sh
curl --noproxy '*' https://check.torproject.org/api/ip
```

Look for `"IsTor": true`. Run this without `sudo` and without a SOCKS option:
a SOCKS request would test the proxy separately from Torando's redirect rules.
Torando-Gui also offers a SOCKS exit check and clearly reports its scope.

## What is covered

The rules cover locally generated traffic owned by the selected UID in the
current network namespace. IPv4 TCP goes to Tor, IPv4 UDP/53 goes to its DNS
listener, and other external IPv4 traffic is blocked. External IPv6 is blocked,
not redirected. UDP applications such as QUIC and many games may stop working.

Loopback remains available. Local proxies, services running under other users,
containers in other network namespaces, and root processes need their own
controls. Existing connections may need to be reopened after enabling.
Firewall managers that reload their rules can remove or reorder Torando's
hooks; check status again after such a reload. The scripts do not persist rules
across reboot.

Torando changes routing, not browser fingerprints or account identity. Use
HTTPS, keep browser security protections enabled, and do not treat one positive
exit check as a guarantee about every application's traffic.

## Upgrading and recovery

If you used the original scripts, disable their rules with your old, edited
`toroff.sh` before replacing the checkout. Version 2 only removes its own
chains; it deliberately leaves those older rules alone. The default Tor DNS
port is now `5353`, so update `torrc` or pass `--dns-port 53` for your existing
listener.

If you made `/etc/resolv.conf` immutable using the old guide, remove that flag
with `sudo chattr -i /etc/resolv.conf` and restore your distribution's normal
resolver configuration. Do not replace a managed symlink blindly. You no
longer need the old browser changes that disabled malware protection.

After a failed enable or disable, run `sudo ./torando.sh --status` and then
`sudo ./toroff.sh` for the same user. A retained guard intentionally blocks that
user's outgoing traffic until cleanup succeeds. Resolve any reported firewall
error and retry; avoid flushing the whole firewall. Keep a separate
administrator session available when changing network rules remotely.

## Development

The firewall tests use a stateful mock and do not change the host's rules:

```sh
python3 -m unittest discover -s tests -v
shellcheck torando.sh toroff.sh lib/torando.sh
```

Torando is licensed under [GPL-3.0](LICENSE).
