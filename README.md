# TORANDO - TOR VPN
<p align="center"> 
<img src="https://github.com/cristiancmoises/torando/assets/86272521/045451b7-545a-4798-9df8-980b122b829d"  width="640"  height="420" />
<center/>
<p/>
         
> <img src="https://github.com/cristiancmoises/torando/assets/86272521/241a6f7f-ba74-4e8d-95f7-9b783ee824fd"  width="30"  height="30" /> 🇧🇷 Para o tutorial em português clique [aqui](https://github.com/cristiancmoises/torando/blob/main/LEIA-ME.md)
_____________________________________________
## Do you need the tor package to run this. Instal tor first!
> DEBIAN:
              
          apt update && apt upgrade && apt install tor torsocks -y
> GENTOO: 
       
          emerge tor torsocks

> ARCH: 
          
         pacman tor torsocks -Syu

> OPENSUSE: 
          
         zypper install tor torsocks -y

## FIRST STEP - CHANGE THE CONFIG
Clone the repo and open the _torando.sh_ and change USERAQUI for your username.
Do the same on _toroff.sh_

    git clone https://github.com/cristiancmoises/torando
    cd torando
    chmod +x *
    nano torando.sh
    
## EDIT TORRC

    nano   /etc/tor/torrc

Then paste in the end:

    VirtualAddrNetwork 10.192.0.0/10
    AutomapHostsOnResolve 1
    TransPort 9040
    DNSPort 53

## NOW EDIT THE RESOLV.CONF

    nano /etc/resolv.conf

## FOR SECURITY

    chattr +i /etc/resolv.conf
    
## THEN REMOVE ALL AND PASTE
    nameserver 127.0.0.1 
    
## FIREFOX CONFIG - NO DNS LEAK
_Go to the firefox and digit *about:config* then press enter._
                
           about:config

> #### OK, Now paste the command and search, then change the value:
|    COMMAND             |     VALUE                        |
|------------------------|----------------------------------|
|network.proxy.socks_remote_dns |  True                     |
|browser.safebrowsing.enabled |    True                     |
|browser.safebrowsing.malware.enabled |   False             |

## NOW YOU CAN TURN ON THE TORANDO.SH!
      cd torando
     ./torando.sh
## FOR DISABLE
     cd torando
    ./toroff.sh

## BONUS! EDIT YOUR BASHRC/FISH OR WHATEVER... 
     nano .bashrc
### INCLUDE:
     alias torando="./torando.sh"
     alias toroff="./offtor.sh"

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=cristiancmoises/torando&type=Date)](https://star-history.com/#cristiancmoises/torando&Date)

## THAT'S ALL! 
![anon](https://github.com/cristiancmoises/torando/assets/86272521/9df06b1d-cff7-4c02-a6fb-c7add5ef27e3)


