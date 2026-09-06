#!/usr/bin/env bash
# Shared implementation for the two command-line entry points.

TORANDO_VERSION=2.0.1
TORANDO_LOCK=/run/torando.lock

torando_die() {
    printf 'Torando: %s\n' "$*" >&2
    exit 1
}

torando_help() {
    cat <<'HELP'
Torando 2.0.1 — route one Linux user's IPv4 TCP and DNS through Tor.

Usage:
  sudo ./torando.sh [--user NAME|UID] [--trans-port PORT] [--dns-port PORT]
  sudo ./toroff.sh [--user NAME|UID]
  sudo ./torando.sh --status [--user NAME|UID]

Options:
  --user NAME|UID   Account to protect; defaults to the user invoking sudo.
  --trans-port N    Tor's local IPv4 TransPort (default: 9040).
  --dns-port N      Tor's local IPv4 DNSPort (default: 5353).
  --status         Inspect the rules without changing them.
  --help           Show this help; root is not required.
  --version        Print the version; root is not required.

Run Tor separately, under a different account, with both listeners bound to
127.0.0.1. Torando does not start Tor or edit torrc. Other non-loopback IPv4
traffic and all non-loopback IPv6 traffic are blocked for the selected UID.
Local services remain accessible; traffic they send under another UID is
outside these rules. Existing unrelated firewall rules are preserved.

Status exits with 0 when enabled, 3 when disabled, and 2 for incomplete or
modified rules. A failed or interrupted update may leave blocking guards;
run toroff.sh for the same user to remove Torando's rules and restore direct
networking. Interruptions exit with 129 (HUP), 130 (INT), or 143 (TERM).
HELP
}

torando_port() {
    if [[ ! $1 =~ ^[0-9]{1,5}$ ]] || ((10#$1 < 1 || 10#$1 > 65535)); then
        torando_die "invalid port: $1 (expected 1–65535)"
    fi
    printf '%d' "$((10#$1))"
}

torando_ipv6_required() {
    local disabled=''
    # An absent proc directory can mean an unloaded IPv6 module. Require the
    # firewall unless the kernel explicitly confirms IPv6 was boot-disabled.
    if [[ -r /sys/module/ipv6/parameters/disable ]]; then
        IFS= read -r disabled </sys/module/ipv6/parameters/disable || true
    fi
    [[ $disabled != 1 && $disabled != Y ]]
}

torando_lock() {
    # /run is root-owned; the lock cannot be planted by an ordinary user.
    umask 077
    exec {TORANDO_LOCK_FD}>"$TORANDO_LOCK"
    flock -n "$TORANDO_LOCK_FD" || torando_die 'another Torando command is running'
}

torando_fw() {
    local binary=$1 table=$2
    shift 2
    "$binary" -w 5 -t "$table" "$@"
}

torando_exists() {
    local result code
    if result=$(torando_fw "$@" 2>&1); then
        return 0
    else
        code=$?
    fi
    # iptables uses 1 for an absent chain or rule; other errors are fatal.
    [[ $code == 1 ]] && return 1
    torando_die "cannot inspect firewall: $result"
}

torando_guard_exists() {
    torando_exists "$1" filter -C OUTPUT -m owner --uid-owner "$TARGET_UID" \
        -m comment --comment "torando:$TARGET_UID:guard" -j REJECT
}

torando_add_guard() {
    # Move the guard to the front even when recovering a failed command.
    torando_fw "$1" filter -I OUTPUT 1 -m owner --uid-owner "$TARGET_UID" \
        -m comment --comment "torando:$TARGET_UID:guard" -j REJECT
}

torando_remove_guards() {
    while torando_guard_exists "$1"; do
        torando_fw "$1" filter -D OUTPUT -m owner --uid-owner "$TARGET_UID" \
            -m comment --comment "torando:$TARGET_UID:guard" -j REJECT
    done
}

torando_unhook() {
    local binary=$1 table=$2 chain=$3
    while torando_exists "$binary" "$table" -C OUTPUT -m owner --uid-owner "$TARGET_UID" -j "$chain"; do
        torando_fw "$binary" "$table" -D OUTPUT -m owner --uid-owner "$TARGET_UID" -j "$chain"
    done
}

torando_reset_chain() {
    local binary=$1 table=$2 chain=$3
    if torando_exists "$binary" "$table" -S "$chain"; then
        torando_fw "$binary" "$table" -F "$chain"
    else
        torando_fw "$binary" "$table" -N "$chain"
    fi
}

torando_delete_chain() {
    local binary=$1 table=$2 chain=$3
    if torando_exists "$binary" "$table" -S "$chain"; then
        torando_fw "$binary" "$table" -F "$chain"
        torando_fw "$binary" "$table" -X "$chain"
    fi
}

torando_hook() {
    torando_fw "$1" "$2" -I OUTPUT 1 -m owner --uid-owner "$TARGET_UID" -j "$3"
}

torando_failed() {
    local code=$?
    trap - EXIT HUP INT TERM
    ((code != 0)) || return 0
    printf 'Torando: firewall update failed (exit %s). Blocking guards may remain.\n' "$code" >&2
    printf 'Recover with: sudo ./toroff.sh --user %s\n' "$TARGET_UID" >&2
    exit "$code"
}

torando_begin_update() {
    # EXIT also covers explicit failures inside inspection helpers. Signals
    # leave any installed guards in place and use the same recovery message.
    trap torando_failed EXIT
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
}

torando_enable() {
    torando_begin_update
    ((IPV6)) && torando_add_guard ip6tables
    torando_add_guard iptables

    # Rebuild only our own chains, with both families blocked throughout.
    torando_reset_chain iptables nat "$NAT_CHAIN"
    torando_reset_chain iptables filter "$FILTER_CHAIN"
    if ((IPV6)); then
        torando_reset_chain ip6tables filter "$FILTER_CHAIN"
    fi

    # DNS comes first so queries to loopback stubs such as 127.0.0.53 are captured.
    torando_fw iptables nat -A "$NAT_CHAIN" -p udp --dport 53 -j REDIRECT --to-ports "$DNS_PORT"
    torando_fw iptables nat -A "$NAT_CHAIN" -d 127.0.0.0/8 -j RETURN
    torando_fw iptables nat -A "$NAT_CHAIN" -p tcp -j REDIRECT --to-ports "$TRANS_PORT"
    torando_fw iptables nat -A "$NAT_CHAIN" -j RETURN
    torando_fw iptables filter -A "$FILTER_CHAIN" -o lo -j ACCEPT
    torando_fw iptables filter -A "$FILTER_CHAIN" -j REJECT
    if ((IPV6)); then
        torando_fw ip6tables filter -A "$FILTER_CHAIN" -o lo -j ACCEPT
        torando_fw ip6tables filter -A "$FILTER_CHAIN" -j REJECT
    fi

    torando_unhook iptables nat "$NAT_CHAIN"
    torando_unhook iptables filter "$FILTER_CHAIN"
    if ((IPV6)); then
        torando_unhook ip6tables filter "$FILTER_CHAIN"
    fi
    torando_hook iptables nat "$NAT_CHAIN"
    torando_hook iptables filter "$FILTER_CHAIN"
    ((IPV6)) && torando_hook ip6tables filter "$FILTER_CHAIN"

    torando_remove_guards iptables
    ((IPV6)) && torando_remove_guards ip6tables
    trap - EXIT HUP INT TERM
    printf 'Torando enabled for UID %s: TCP → 127.0.0.1:%s, DNS → 127.0.0.1:%s.\n' \
        "$TARGET_UID" "$TRANS_PORT" "$DNS_PORT"
}

torando_disable() {
    torando_begin_update
    ((IPV6)) && torando_add_guard ip6tables
    torando_add_guard iptables
    torando_unhook iptables nat "$NAT_CHAIN"
    torando_unhook iptables filter "$FILTER_CHAIN"
    ((IPV6)) && torando_unhook ip6tables filter "$FILTER_CHAIN"
    torando_delete_chain iptables nat "$NAT_CHAIN"
    torando_delete_chain iptables filter "$FILTER_CHAIN"
    ((IPV6)) && torando_delete_chain ip6tables filter "$FILTER_CHAIN"
    torando_remove_guards iptables
    ((IPV6)) && torando_remove_guards ip6tables
    trap - EXIT HUP INT TERM
    printf 'Torando disabled for UID %s; direct networking restored.\n' "$TARGET_UID"
}

torando_top_hook() {
    local rules line
    rules=$(torando_fw "$1" "$2" -S OUTPUT) || return 1
    while IFS= read -r line; do
        if [[ $line == '-A '* ]]; then
            if [[ $line == "-A OUTPUT -m owner --uid-owner $TARGET_UID -j $3" ]]; then
                return 0
            fi
            # Other protected users may have been enabled after this one.
            if [[ $line =~ ^-A\ OUTPUT\ -m\ owner\ --uid-owner\ ([0-9]+)\ -j\ TORANDO_[NF]_([0-9]+)$ ]] &&
                [[ ${BASH_REMATCH[1]} == "${BASH_REMATCH[2]}" && ${BASH_REMATCH[1]} != "$TARGET_UID" ]]; then
                continue
            fi
            return 1
        fi
    done <<<"$rules"
    return 1
}

torando_chain_matches() {
    local rules line actual=''
    rules=$(torando_fw "$1" "$2" -S "$3") || return 1
    while IFS= read -r line; do
        [[ $line == '-A '* ]] || continue
        # iptables-save spells out these implicit protocol/reject defaults.
        line=${line// -m tcp/}
        line=${line// -m udp/}
        line=${line// --reject-with icmp-port-unreachable/}
        line=${line// --reject-with icmp6-port-unreachable/}
        actual+="$line"$'\n'
    done <<<"$rules"
    [[ $actual == "$4" ]]
}

torando_filter_complete() {
    local expected
    printf -v expected -- '-A %s -o lo -j ACCEPT\n-A %s -j REJECT\n' "$FILTER_CHAIN" "$FILTER_CHAIN"
    torando_top_hook "$1" filter "$FILTER_CHAIN" &&
        torando_chain_matches "$1" filter "$FILTER_CHAIN" "$expected"
}

torando_status() {
    local binary table chain any=0 rules line expected dns='' trans=''
    for binary in "${FIREWALLS[@]}"; do
        if torando_guard_exists "$binary"; then
            printf 'Torando incomplete for UID %s: a blocking guard is active.\n' "$TARGET_UID"
            return 2
        fi
        for table in filter nat; do
            [[ $binary != ip6tables || $table != nat ]] || continue
            chain=$FILTER_CHAIN
            [[ $table != nat ]] || chain=$NAT_CHAIN
            if torando_exists "$binary" "$table" -S "$chain"; then
                any=1
            fi
        done
    done
    if (( ! any )); then
        printf 'Torando disabled for UID %s.\n' "$TARGET_UID"
        return 3
    fi

    if torando_exists iptables nat -S "$NAT_CHAIN"; then
        rules=$(torando_fw iptables nat -S "$NAT_CHAIN")
        while IFS= read -r line; do
            if [[ $line =~ --to-ports\ ([0-9]+) ]]; then
                if [[ $line == *' -p udp '* ]]; then
                    dns=${BASH_REMATCH[1]}
                elif [[ $line == *' -p tcp '* ]]; then
                    trans=${BASH_REMATCH[1]}
                fi
            fi
        done <<<"$rules"
    fi
    printf -v expected -- '-A %s -p udp --dport 53 -j REDIRECT --to-ports %s\n-A %s -d 127.0.0.0/8 -j RETURN\n-A %s -p tcp -j REDIRECT --to-ports %s\n-A %s -j RETURN\n' \
        "$NAT_CHAIN" "$dns" "$NAT_CHAIN" "$NAT_CHAIN" "$trans" "$NAT_CHAIN"
    if [[ -n $dns && -n $trans ]] &&
        torando_top_hook iptables nat "$NAT_CHAIN" &&
        torando_chain_matches iptables nat "$NAT_CHAIN" "$expected" &&
        torando_filter_complete iptables &&
        { (( ! IPV6 )) || torando_filter_complete ip6tables; }; then
        printf 'Torando enabled for UID %s: TCP port %s, DNS port %s.\n' "$TARGET_UID" "$trans" "$dns"
        return 0
    fi
    printf 'Torando incomplete or modified for UID %s; run torando.sh to repair or toroff.sh to remove.\n' "$TARGET_UID"
    return 2
}

torando_main() {
    local action=$1 target=${SUDO_USER:-${SUDO_UID:-}} dependency service service_uid code
    shift
    TRANS_PORT=9040
    DNS_PORT=5353
    while (($#)); do
        case $1 in
            --help|-h) torando_help; return 0 ;;
            --version) printf '%s\n' "$TORANDO_VERSION"; return 0 ;;
            --status) action=status; shift ;;
            --user|--trans-port|--dns-port)
                (($# >= 2)) || torando_die "missing value for $1"
                case $1 in
                    --user) target=$2 ;;
                    --trans-port) TRANS_PORT=$(torando_port "$2") ;;
                    --dns-port) DNS_PORT=$(torando_port "$2") ;;
                esac
                shift 2
                ;;
            *) torando_die "unknown argument: $1 (see --help)" ;;
        esac
    done
    [[ $(uname -s) == Linux ]] || torando_die 'this version supports Linux only'
    [[ $(id -u) == 0 ]] || torando_die 'run with sudo or as root (see --help)'
    [[ -n $target ]] || torando_die 'choose an account with --user NAME or invoke through sudo'
    TARGET_UID=$(id -u -- "$target" 2>/dev/null) || torando_die "unknown account: $target"
    [[ $TARGET_UID =~ ^[0-9]+$ && $TARGET_UID != 0 ]] || torando_die 'refusing to redirect the root account'
    for service in tor debian-tor _tor; do
        if service_uid=$(id -u -- "$service" 2>/dev/null) && [[ $TARGET_UID == "$service_uid" ]]; then
            torando_die "refusing to redirect Tor service account $service"
        fi
    done
    for dependency in iptables flock pgrep; do
        command -v "$dependency" >/dev/null || torando_die "required command is missing: $dependency"
    done
    if [[ $action == enable ]]; then
        if pgrep -u "$TARGET_UID" -x tor >/dev/null; then
            torando_die 'the selected account is running Tor; choose the application user instead'
        else
            code=$?
            [[ $code == 1 ]] || torando_die 'could not check the account for a running Tor process'
        fi
    fi
    IPV6=0
    FIREWALLS=(iptables)
    if torando_ipv6_required; then
        command -v ip6tables >/dev/null || torando_die 'IPv6 protection is required but ip6tables is missing; no rules changed'
        IPV6=1
        FIREWALLS+=(ip6tables)
    fi
    FILTER_CHAIN=TORANDO_F_$TARGET_UID
    NAT_CHAIN=TORANDO_N_$TARGET_UID
    torando_lock
    torando_fw iptables nat -S OUTPUT >/dev/null
    for dependency in "${FIREWALLS[@]}"; do
        torando_fw "$dependency" filter -S OUTPUT >/dev/null
    done
    case $action in
        enable) torando_enable ;;
        disable) torando_disable ;;
        status) torando_status ;;
    esac
}
