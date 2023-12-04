sudo iptables -t nat -A OUTPUT -p tcp -m owner --uid-owner USERAQUI -m tcp -j RED>
sudo iptables -t nat -A OUTPUT -p udp -m owner --uid-owner USERAQUI -m udp --dpor>
sudo iptables -t filter -A OUTPUT -p tcp -m owner --uid-owner USERAQUI -m tcp --d>
sudo iptables -t filter -A OUTPUT -p udp -m owner --uid-owner USERAQUI -m udp --d>
sudo iptables -t filter -A OUTPUT -m owner --uid-owner USERAQUI -j DROP
