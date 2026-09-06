# Torando

O Torando encaminha as conexões TCP IPv4 de um usuário Linux pela rede Tor e
bloqueia o restante do tráfego externo desse usuário. Você pode ativar e
desativar o encaminhamento pelo terminal, sem editar comandos de firewall.

**[Torando-Gui](https://github.com/cristiancmoises/torando-gui) é a interface
gráfica do Torando.** Ele oferece controles de conexão, consulta do IP de saída
e configurações. O aplicativo instala seu próprio serviço e não depende destes
scripts. Use apenas um dos dois para controlar o mesmo usuário de cada vez.

[English](README.md) · [FreeBSD](freebsd.md) · [Segurança](SECURITY.md)

## O que mudou na versão 2.0.0

O nome de usuário agora é informado com `--user`; não há mais `USERAQUI` para
substituir. Os comandos podem ser repetidos sem duplicar regras, usam cadeias
próprias e preservam as demais regras do firewall. O tráfego IPv6 externo do
usuário também é bloqueado. Se uma alteração falhar depois de instalar uma
regra de bloqueio temporária, ela permanece até a recuperação.

## Preparação

Você precisa de Linux, Bash, `iptables`, `ip6tables` salvo se IPv6 estiver desativado na
inicialização do kernel, `flock` do util-linux, `pgrep` do procps e Tor executando em uma conta separada.
Em Debian ou Ubuntu:

```sh
sudo apt update
sudo apt install tor iptables util-linux procps
```

Em outras distribuições, instale os pacotes equivalentes. Os scripts não
instalam nem iniciam o serviço Tor.

Edite o arquivo `torrc` do serviço, normalmente `/etc/tor/torrc`, e adicione ou
ajuste estas opções uma única vez:

```text
SocksPort 127.0.0.1:9050
TransPort 127.0.0.1:9040
DNSPort 127.0.0.1:5353
VirtualAddrNetworkIPv4 10.192.0.0/10
AutomapHostsOnResolve 1
```

Mantenha as portas acessíveis apenas pelo loopback. Confira a configuração e
reinicie o Tor. Em uma instalação comum com systemd:

```sh
sudo tor --verify-config -f /etc/tor/torrc
sudo systemctl restart tor
```

As consultas UDP IPv4 na porta 53 feitas pelo usuário são redirecionadas para
o DNS do Tor, inclusive quando destinadas a um resolvedor no loopback. Não é
preciso alterar `/etc/resolv.conf` nem torná-lo imutável. Consultas delegadas por
socket Unix a um serviço de outro usuário ficam fora dessas regras; confira
como seu sistema resolve nomes. O DNS do Tor aceita consultas A, AAAA e PTR,
conforme o [manual do Tor](https://man.freebsd.org/cgi/man.cgi?manpath=freebsd-ports&query=tor&sektion=1).

## Ativar e desativar

Feche os aplicativos com conexões abertas antes de ativar. Sockets UDP de DNS
já existentes podem manter o mapeamento de conntrack para o resolvedor anterior,
inclusive no loopback. Reabra os aplicativos depois de instalar as regras.

```sh
git clone https://github.com/cristiancmoises/torando.git
cd torando
./torando.sh --version
sudo ./torando.sh
sudo ./torando.sh --status
sudo ./toroff.sh
```

Sem `--user`, o comando usa o usuário que chamou `sudo`. Para escolher outro
usuário ou executar a partir de um terminal root:

```sh
sudo ./torando.sh --user alice
sudo ./torando.sh --status --user alice
sudo ./toroff.sh --user alice
```

Não selecione root nem a conta que executa o Tor. Para usar portas diferentes,
combine os valores com seu `torrc`:

```sh
sudo ./torando.sh --trans-port 9041 --dns-port 5354
```

Use `./torando.sh --help` para ver as opções. `--status` confere as regras do
firewall, não a conexão com a rede Tor. Seu código de saída é `0` quando ativo,
`3` quando desativado e `2` quando as regras estão incompletas ou alteradas.

Para conferir uma conexão nova, execute no terminal do usuário selecionado,
sem `sudo` e sem configurar um proxy SOCKS:

```sh
curl --noproxy '*' https://check.torproject.org/api/ip
```

A resposta deve conter `"IsTor": true`. Uma consulta feita com `--socks5-hostname`
testaria o proxy separadamente, sem confirmar o redirecionamento do Torando.

## Limites do encaminhamento

As regras valem para o tráfego local do UID selecionado no namespace de rede
atual. TCP IPv4 vai para o Tor; UDP IPv4 na porta 53 vai para o DNS do Tor. O
restante do tráfego IPv4 externo e todo o IPv6 externo são bloqueados. Jogos,
QUIC e outros aplicativos que dependem de UDP podem parar de funcionar.

O loopback continua disponível. Proxies locais, serviços de outros usuários,
processos root e contêineres em outros namespaces precisam de controles
próprios. Abra novamente as conexões que já estavam em andamento. As regras
não persistem após reiniciar a máquina. Se outro gerenciador recarregar o
firewall, confira o status novamente.

O Torando não esconde a identidade de contas nem a impressão digital do
navegador. Use HTTPS e mantenha as proteções de segurança do navegador ativadas.
Uma consulta positiva de IP não comprova o caminho de todos os aplicativos.

## Atualização e recuperação

Se você usa os scripts antigos, desative suas regras com a cópia antiga e já
editada do `toroff.sh` antes de atualizar. A versão 2 só remove suas próprias
cadeias. O DNS agora usa a porta `5353` por padrão; atualize o `torrc` ou passe
`--dns-port 53` para manter uma configuração existente.

Se seguiu o guia antigo e tornou `/etc/resolv.conf` imutável, remova a trava com
`sudo chattr -i /etc/resolv.conf` e restaure a configuração normal do resolvedor
da distribuição. Preserve os links simbólicos gerenciados pelo sistema.
Reative também a proteção contra malware do navegador caso tenha seguido a
recomendação antiga de desativá-la.

Após uma falha, confira `sudo ./torando.sh --status` e execute
`sudo ./toroff.sh` para o mesmo usuário. Resolva o erro informado e tente
novamente. O bloqueio temporário permanece até a limpeza terminar; não limpe o
firewall inteiro para removê-lo. Em acesso remoto, mantenha outra sessão de
administração disponível.

O [README em inglês](README.md#development) explica como executar os testes
sem alterar o firewall da máquina. Licença: [GPL-3.0](LICENSE).
