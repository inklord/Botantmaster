import os
import platform
import subprocess
import time
import sys
import signal

def find_and_kill_process(name):
    """Busca y termina un proceso por nombre"""
    system = platform.system()
    
    print(f"Buscando procesos de {name}...")
    
    if system == "Windows":
        # Buscar el PID del proceso
        try:
            # Buscar procesos python con el nombre especificado
            output = subprocess.check_output(["tasklist", "/FI", f"IMAGENAME eq python.exe"], text=True)
            lines = output.strip().split('\n')
            
            pids = []
            for line in lines[3:]:  # Saltar el encabezado
                parts = line.split()
                if len(parts) >= 2:
                    pid = parts[1]
                    # Verificar si este proceso está ejecutando nuestro script
                    try:
                        cmd_output = subprocess.check_output(["wmic", "process", "where", f"ProcessId={pid}", "get", "CommandLine"], text=True)
                        if name in cmd_output:
                            pids.append(pid)
                            print(f"Encontrado proceso {name} con PID {pid}")
                    except:
                        pass
            
            # Terminar los procesos encontrados
            for pid in pids:
                try:
                    print(f"Terminando proceso con PID {pid}...")
                    subprocess.run(["taskkill", "/F", "/PID", pid], check=True)
                    print(f"Proceso con PID {pid} terminado")
                except subprocess.CalledProcessError:
                    print(f"No se pudo terminar el proceso con PID {pid}")
        
        except subprocess.CalledProcessError as e:
            print(f"Error al buscar procesos: {e}")
    
    else:  # Linux/Mac
        try:
            output = subprocess.check_output(["pgrep", "-f", name], text=True)
            pids = output.strip().split('\n')
            
            for pid in pids:
                if pid:
                    print(f"Terminando proceso con PID {pid}...")
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        time.sleep(1)
                        print(f"Proceso con PID {pid} terminado")
                    except ProcessLookupError:
                        print(f"No se pudo encontrar el proceso con PID {pid}")
        except subprocess.CalledProcessError:
            print("No se encontraron procesos existentes.")

def start_bot():
    """Inicia el bot"""
    print("Iniciando AntmasterBot...")
    
    system = platform.system()
    if system == "Windows":
        # Iniciar en una nueva ventana y sin bloquear este script
        subprocess.Popen(["start", "cmd", "/k", "python", "AntmasterBot.py"], shell=True)
    else:  # Linux/Mac
        # Iniciar en segundo plano
        subprocess.Popen(["python", "AntmasterBot.py", "&"], shell=True)
    
    print("Bot iniciado en segundo plano.")

if __name__ == "__main__":
    print("=== Reiniciando AntmasterBot ===")
    
    # Paso 1: Detener cualquier instancia existente
    find_and_kill_process("AntmasterBot.py")
    
    # Paso 2: Esperar un momento para asegurarse de que los procesos se terminaron
    print("Esperando 3 segundos...")
    time.sleep(3)
    
    # Paso 3: Iniciar el bot
    start_bot()
    
    print("=== Proceso de reinicio completado ===")
    print("El bot debería estar funcionando ahora. Verifica Telegram para confirmar.") 