import paramiko
import argparse
import sys
from enum import Enum


class OsType(Enum):
    ALMA = "alma"
    DEBIAN = "debian"
    UNKNOWN = "unknown"


# Тип для хранения информации о загруженности сервера
# class ServersInfo(TypedDict):
#     hostname: str
#     cpu_load: float


# Определяем тип операционной системы целевого хоста
# try:
#     with paramiko.SSHClient() as client:
#         client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#         client.connect(min_load_host, username="root", timeout=10)
#         os_type_host = detect_os_type(client)
# except Exception as e:
#     eprint(f"Не удалось подключиться к серверу {host}: {e}")
#     os_type_host = OsType.UNKNOWN

#     commands = [
#     "find / -type f -name postgresql.conf",
#     """sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" /etc/postgresql/15/main/postgresql.conf""",
# ]


# Функция для вывода в stderr
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


# Функция для разбора аргументов командной строки
def prepare_parser():
    parser = argparse.ArgumentParser(
        description="Программа для установки PostgreSQL на наименее загруженном сервере"
    )
    parser.add_argument("-s", "--servers", help="Hostnames divided by comma")
    return parser


def exec_ssh_command(client: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    """Функция для выполнения команды на сервере"""

    _, stdout, stderr = client.exec_command(command, get_pty=True)
    exit_status = stdout.channel.recv_exit_status()
    output = stdout.read().decode().strip()
    error = stderr.read().decode().strip()
    return exit_status, output, error


def get_cpu_load(client: paramiko.SSHClient, host: str) -> float:
    """Функция для получения загруженности сервера"""
    print(f"Определяем загруженность сервера {host}...")
    try:
        _, output, _ = exec_ssh_command(
            client, "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"
        )
        cpu_load = float(output)
        print(f"Загруженность сервера {host}: {cpu_load}")
        return cpu_load
    except Exception as e:
        eprint(f"Не удалось получить загруженность сервера {host}: {e}")
        return float(
            "inf"
        )  # Возвращаем очень большое число, чтобы указать, что сервер недоступен


def detect_os_type(client: paramiko.SSHClient, host: str) -> OsType:
    """Функция для определения типа операционной системы на сервере"""

    print(f"Определяем тип операционной системы на сервере {host}...")
    try:
        _, output, _ = exec_ssh_command(client, "cat /etc/os-release")
        if "AlmaLinux" in output:
            return OsType.ALMA
        elif "Debian" in output:
            return OsType.DEBIAN
        else:
            return OsType.UNKNOWN
    except Exception as e:
        eprint(f"Не удалось определить тип операционной системы на сервере {host}: {e}")
        return OsType.UNKNOWN


def install_postgresql(client: paramiko.SSHClient, host: str, os_type: OsType):
    """Функция для установки PostgreSQL на сервере"""

    print(f"Устанавливаем PostgreSQL на сервере {host} ({os_type.value})...")
    if os_type == OsType.DEBIAN:
        commands = [
            "apt-get update && apt-get upgrade -y",
            "apt-get install -y postgresql postgresql-contrib",
            "systemctl start postgresql",
            "systemctl enable postgresql",
        ]
    elif os_type == OsType.ALMA:
        commands = [
            "dnf update -y",
            "dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-9-x86_64/pgdg-redhat-repo-latest.noarch.rpm",
            "dnf install -y postgresql17-server",
            "/usr/pgsql-17/bin/postgresql-17-setup initdb",
            "systemctl enable postgresql-17",
            "systemctl start postgresql-17",
        ]
    else:
        eprint(
            "Ошибка при установке PostgreSQL на сервер: неподерживаемый тип операционной системы"
        )
        return
    for command in commands:
        print(f"Выполняем команду: {command}...")
        exit_status, output, error = exec_ssh_command(client, command)
        if output:
            print(output)
        if exit_status != 0:
            eprint(f"Ошибка при установке PostgreSQL на сервере {host}: {error}")
            return

    print(f"PostgreSQL успешно установлен на сервере {host}")


def open_external_connections_postgresql(
    client: paramiko.SSHClient, host: str, os_type: OsType
):
    """Функция настройки PostgreSQL для приёма внешних соединений"""

    print(
        f"Настраиваем приём внешних соединений PostgreSQL на сервере {host} ({os_type.value})..."
    )

    # Ищем файл postgresql.conf
    command = "find / -type f -name postgresql.conf"
    exit_status, output, error = exec_ssh_command(client, command)

    if exit_status != 0:
        eprint(
            f"Ошибка при поиске файла postgresql.conf на сервере {host}: {error}"
        )
        return

    pg_conf_path = output

    # Изменяем файл postgresql.conf для приёма внешних соединений
    command = f"""sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" {pg_conf_path}"""
    exit_status, output, error = exec_ssh_command(client, command)

    if exit_status != 0:
        eprint(
            f"Ошибка при изменении файла postgresql.conf на сервере {host}: {error}"
        )
        return

    # Ищем файл pg_hba.conf
    command = "find / -type f -name pg_hba.conf"
    exit_status, output, error = exec_ssh_command(client, command)

    if exit_status != 0:
        eprint(
            f"Ошибка при поиске файла pg_hba.conf на сервере {host}: {error}"
        )
        return

    pg_hba_path = output

    # Изменяем файл pg_hba.conf для приёма внешних соединений
    lines_to_add = [
        "host    all             all             0.0.0.0/0               trust",
        "host    all             all             ::0/0                   trust",
    ]

    for line in lines_to_add:
        command = f"echo {line} | tee -a {pg_hba_path} > /dev/null"
        exit_status, output, error = exec_ssh_command(client, command)

        if exit_status != 0:
            eprint(
                f"Ошибка при изменении файла pg_hba.conf на сервере {host}: {error}"
            )
            return
        
    # Перезагружаем сервер PostgreSQL
    command = "systemctl restart postgresql"
    exit_status, output, error = exec_ssh_command(client, command)

    if exit_status != 0:
        eprint(
            f"Ошибка при перезапуске демона PostgreSQL на сервере {host}: {error}"
        )
        return

    print(f"Приём внешних соединений PostgreSQL успешно установлен на сервере {host}")


def main():

    # Разбираем аргументы командной строки
    parser = prepare_parser()
    args = parser.parse_args()

    if not args.servers:
        eprint("Не указаны серверы")
        return

    hosts = args.servers.split(",")

    # Проверяем загруженность серверов
    servers_info = {}
    for host in hosts:
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, username="root", timeout=10)
            print(f"Соединились по SSH с сервером {host}")

            cpu_load = get_cpu_load(client, host)
            os_type = detect_os_type(client, host)

            servers_info[host] = {
                "ssh_client": client,
                "cpu_load": cpu_load,
                "os_type": os_type,
            }
        except Exception as e:
            eprint(f"Не удалось подключиться к серверу {host}: {e}")

    if not servers_info:
        eprint("Нет доступных серверов для установки PostgreSQL")
        return

    # Отбираем только серверы с поддерживаемой ОС
    valid_servers = {
        host: server_info
        for host, server_info in servers_info.items()
        if server_info["os_type"] != OsType.UNKNOWN
        and server_info["cpu_load"] != float("inf")
    }

    # Выбираем наименнее загруженный сервер
    min_load_host = min(valid_servers.items(), key=lambda x: x[1]["cpu_load"])

    print(min_load_host)

    # Устанавливаем PostgreSQL на сервер
    install_postgresql(
        min_load_host[1]["ssh_client"], min_load_host[0], min_load_host[1]["os_type"]
    )

    # Настраиваем PostgreSQL целевого хоста для приема внешних соединений
    open_external_connections_postgresql(
        min_load_host[1]["ssh_client"], min_load_host[0], min_load_host[1]["os_type"]
    )

    # Закрываем соединение с сервером
    for host, server_info in servers_info.items():
        if server_info["ssh_client"]:
            server_info["ssh_client"].close()


if __name__ == "__main__":
    main()
