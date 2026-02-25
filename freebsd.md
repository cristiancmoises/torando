# **TORANDO: Running Tor as a Transparent Proxy on FreeBSD**
<img width="891" height="392" alt="2026-02-25_20-45" src="https://github.com/user-attachments/assets/4e1ab89c-8695-4227-a0f9-60ab7e649433" />

This tutorial shows you how to run **Tor** on **FreeBSD** and configure it as a **transparent proxy**, effectively routing all HTTP/HTTPS traffic through the Tor network, similar to how a VPN works.

## **1. Install Tor on FreeBSD**

First, install **Tor** on your FreeBSD machine using the following command:

    pkg install tor

## **2. Configure the `torrc` File**

After installing Tor, you need to configure it. The `torrc` file is where you define the settings for Tor. Edit the `/usr/local/etc/tor/torrc` file:

    nano /usr/local/etc/tor/torrc

Here’s the recommended configuration for using Tor as a transparent proxy:

### /usr/local/etc/tor/torrc  
  
#### Enable the SOCKS Proxy (for applications that support SOCKS)  
    SocksPort 127.0.0.1:9050  
  
#### Set up a transparent proxy to route all traffic through Tor (like a VPN)  
    TransPort 9040  
    DNSPort 5353

-   **SocksPort**: This is the standard SOCKS proxy port (for apps that support SOCKS).
    
-   **TransPort**: This enables transparent proxying to route all TCP traffic through Tor (on port 9040).
    
-   **DNSPort**: Tor provides a local DNS server to handle DNS queries through the network (port 5353).
    

Save the file after editing.

## **3. Configure FreeBSD’s Firewall (`pf`)**

We’ll now configure the **pf** firewall to redirect all traffic on HTTP (port 80) and HTTPS (port 443) through Tor's transparent proxy.

Edit the `/etc/pf.conf` file:

sudo nano /etc/pf.conf

Add the following rules:

    /etc/pf.conf  
  
##### Skip loopback interface  
    set skip on lo  
  
##### Redirect HTTP traffic (port 80) to Tor's transparent proxy (port 9040)  
    rdr pass on lo0 inet proto tcp from any to any port 80  -> 127.0.0.1 port 9040  
  
##### Redirect HTTPS traffic (port 443) to Tor's transparent proxy (port 9040)  
    rdr pass on lo0 inet proto tcp from any to any port 443  -> 127.0.0.1 port 9040

-   **`rdr pass on lo0`**: Redirects traffic on the **loopback interface (lo0)**.
    
-   **`proto tcp`**: Applies the rule to TCP traffic.
    
-   **`port 80` and `port 443`**: Redirects HTTP and HTTPS traffic.
    
-   **`-> 127.0.0.1 port 9040`**: Redirects the traffic to the **local Tor proxy** (port 9040).
    

Save the file after editing.

## **4. Reload the Firewall Rules**

Now that we’ve updated the `pf.conf` file, reload the firewall configuration to apply the changes:
    
    pfctl -f /etc/pf.conf # Load the new pf.conf configuration  
    pfctl -e  # Enable pf (if not already enabled)

Verify that `pf` is running:

    pfctl -s info

You should see information about the `pf` status, including if it’s enabled.

## **5. Start the Tor Service**

Next, ensure that the **Tor** service is running. Start it with:

    service tor start

If you want to run Tor in the foreground for debugging or testing, you can also start it manually:

tor

You can check the Tor logs for any errors or issues:

    tail -f /var/log/tor/log

## **6. Verify the Transparent Proxy Setup**

#### **Test with Curl**

To verify that all your traffic is routed through Tor, use `curl` to check the Tor network:

    curl  --socks5  127.0.0.1:9050 https://check.torproject.org/

If everything is set up correctly, it will confirm that you're connected to the Tor network.


Check that your IP address is being anonymized by visiting a site like [WhatIsMyIP](https://www.whatismyip.com) or [CheckTor](https://check.torproject.org) or [IpCheckIng](https://ip.securityops.co).

#### **Verify the Firewall Rules**

To verify that the traffic is being correctly routed through the Tor network, you can use `pfctl` to check the rules applied by pf:
 
    pfctl -sr

Ensure that the redirect rules are listed, and they point to the correct port (`9040`).


## **7. Ensuring Permanent DNS Configuration (`/etc/resolv.conf`) on FreeBSD**

To make sure `127.0.0.1` is always used as the nameserver in FreeBSD and prevent it from being overwritten (e.g., by DHCP or network managers), follow these steps:

#### **1. Disable DHCP Overwriting `/etc/resolv.conf`**

If you're using **DHCP**, you need to configure it to avoid overwriting the DNS settings.

1.  Edit the **DHCP client configuration file**:
    
       
        nano /etc/dhclient.conf
    
2.  Add the following line to **force** `127.0.0.1` as the DNS server:
    
    supersede domain-name-servers 127.0.0.1;
    
3.  Restart the network interface or DHCP client to apply the changes:
    
        service netif restart  
        service dhclient restart
    

#### **2. Make `/etc/resolv.conf` Immutable**

To prevent `/etc/resolv.conf` from being modified by any process, make the file **immutable**:

1.  Edit `/etc/resolv.conf` to set `127.0.0.1` as the nameserver:
    
    sudo nano /etc/resolv.conf
    
    Add the following line:
    
    
        nameserver 127.0.0.1
    
2.  Set the file as **immutable**:
    

       
        chattr +i /etc/resolv.conf
    
3.  Verify that the file is immutable:
    
      
        lsattr /etc/resolv.conf
    
    You should see `i` in the output:
    
    ----i-------- /etc/resolv.conf
    

#### **3. (Optional) Use `resolvconf` to Manage DNS**

If you're using `resolvconf` to manage DNS, configure it to use `127.0.0.1` as the nameserver:

1.  Install `resolvconf` if it's not installed:
    
        pkg install resolvconf
    
2.  Enable and configure `resolvconf`:
    
    sudo sysrc resolvconf_enable="YES"
    
3.  Edit `/etc/resolvconf.conf` to specify the nameserver:
    

        nano /etc/resolvconf.conf
    
    Add the line:
    
      
        nameserver=127.0.0.1
    
4.  Restart the `resolvconf` service:
    
      
        service resolvconf restart

----------

This section will ensure that **127.0.0.1** remains the permanent nameserver on FreeBSD, preventing it from being overwritten by DHCP or other network management tools.

----------

----------

#### **Summary of Steps**

1.  **Install Tor** on FreeBSD: `sudo pkg install tor`.
    
2.  **Edit `torrc`** to enable transparent proxying via `TransPort` and `DNSPort`.
    
3.  **Configure `pf`** to redirect traffic on ports 80 and 443 to Tor's transparent proxy (port 9040).
    
4.  **Reload the firewall**: `sudo pfctl -f /etc/pf.conf` and `sudo pfctl -e`.
    
5.  **Start the Tor service**: `sudo service tor start`.
    
6.  **Test your configuration** using `curl` or a browser configured to use Tor.

7.  **Permanent nameserver**
----------

#### **Important Notes**

-   **Firewall Rules**: These rules only redirect **HTTP** (port 80) and **HTTPS** (port 443) traffic. If you want to route additional ports through Tor (like for DNS or other protocols), you need to add more rules to `pf.conf`.
    
-   **Speed**: Keep in mind that Tor is **slower** than traditional VPNs because it routes traffic through multiple relays. It is designed for **anonymity**, not speed.
    
-   **Security**: While Tor anonymizes your traffic, it does not guarantee **full security**. Always use **HTTPS** to ensure your traffic is encrypted and protected from exit node eavesdropping.
