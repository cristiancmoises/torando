# TORANDO - TOR VPN
<p align="center"> 
<img src="https://github.com/cristiancmoises/torando/assets/86272521/045451b7-545a-4798-9df8-980b122b829d"  width="640"  height="420" />
<center/>
<p/>
  
### Você precisa do pacote do tor instalado! Vamos instalar!

> DEBIAN:
              
          apt update && apt upgrade && apt install tor torsocks -y
> GENTOO: 
       
          emerge tor torsocks

> ARCH: 
          
         pacman tor torsocks -Syu

> OPENSUSE: 
          
         zypper install tor torsocks -y

## PRIMEIRO PASSO! ALTERE A CONFIG
Clone o repositório então edite _torando.sh_ e mude USERAQUI para o seu nome de usuário.
Faça o mesmo em _toroff.sh_

    git clone https://github.com/cristiancmoises/torando
    cd torando
    chmod +x *
    nano torando.sh
    
## EDITE O TORRC

    nano   /etc/tor/torrc

E cole este código no final:

    VirtualAddrNetwork 10.192.0.0/10
    AutomapHostsOnResolve 1
    TransPort 9040
    DNSPort 53

## AGORA EDITE O RESOLV.CONF

    nano /etc/resolv.conf

## REMOVA TUDO E COLE
    nameserver 127.0.0.1

## POR SEGURANÇA
    chattr +i /etc/resolv.conf
 
    
## FIREFOX CONFIG - SEM VAZAMENTO DE DNS
_Vá para o firefox e digite *about:config* e pressione enter._
![image](https://github.com/cristiancmoises/torando/assets/86272521/149b910f-baab-44c8-b11d-35ca0b409a52)
                
           about:config

> #### OK, Agora na pesquisa digite o comando e altere:
![image](https://github.com/cristiancmoises/torando/assets/86272521/2951cc34-501a-4ffb-8eb8-07299fd83a92)

|    COMANDO             |     VALOR                        |
|------------------------|----------------------------------|
|network.proxy.socks_remote_dns |  True                     |
|browser.safebrowsing.enabled |    True                     |
|browser.safebrowsing.malware.enabled |   False             |

## AGORA VOCÊ JÁ PODE INICIAR O TORANDO.SH!
      cd torando
     ./torando.sh
## PARA DESATIVAR
     cd torando
    ./toroff.sh

## BONUS! EDITE SEU BASHRC/FISH OU OUTRO... 
     nano .bashrc
### INCLUA NO FINAL:
     alias torando="./torando.sh"
     alias toroff="./offtor.sh"

## ISTO É TUDO! 
![anon](https://github.com/cristiancmoises/torando/assets/86272521/d02ee4f6-83ee-4a43-abd9-a11c9e37c77d)


