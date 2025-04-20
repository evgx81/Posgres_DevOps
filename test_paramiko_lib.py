import paramiko
import statistics


def get_cpuloadavg(command_result):
    return statistics.mean(
        list(map(float, command_result.split("load average:")[-1].strip().split(", ")))
    )


def exec_commands_on_remote_server(hostname, username, password, commands):

    command_results = []

    # Создаем объект SSHClient
    with paramiko.SSHClient() as client:

        # Устанавливаем политику подключения (не рекомендуется для продакшена)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Подключаемся к серверу
        client.connect(hostname, username=username)

        for command in commands:

            stdin, stdout, stderr = client.exec_command(command, get_pty=True)

            if "sudo" in command:  
                stdin.write(password + "\n")
                stdin.flush()

            # stdin.close()
            # stderr.close()
            # print(stderr.read().decode().rstrip())

            command_results.append(stdout.read().decode().rstrip())

    return command_results


if __name__ == "__main__":

    alma_conf = {
        "hostname": "192.168.1.71",
        "username": "www",
        "password": "Www_12343412",
    }

    debian_conf = {
        "hostname": "192.168.1.68",
        "username": "www",
        "password": "Www_12343412",
    }

    # Получаем среднее значение загрузки процессора на серверах
    alma_cpuloadavg = get_cpuloadavg(
        exec_commands_on_remote_server(
            alma_conf["hostname"],
            alma_conf["username"],
            alma_conf["password"],
            ["uptime"],
        )[0]
    )

    debian_cpuloadavg = get_cpuloadavg(
        exec_commands_on_remote_server(
            debian_conf["hostname"],
            debian_conf["username"],
            debian_conf["password"],
            ["uptime"],
        )[0]
    )

    print(alma_cpuloadavg)
    print(debian_cpuloadavg)

    # if alma_cpuloadavg > debian_cpuloadavg:

    # postgres_commands_install = [
    #     "sudo apt update && sudo apt upgrade",
    #     "sudo apt install -y postgresql-common",
    #     "sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh",
    #     "sudo systemctl status postgresql",
    # ]

    # print(exec_commands_on_remote_server(
    #     debian_conf["hostname"],
    #     debian_conf["username"],
    #     debian_conf["password"],
    #     postgres_commands_install,
    # ))

    # else:

    #     postgres_commands_install = [
    #         "dnf install postgresql-server",
    #           "sudo -u postgres createuser -e student"
    #     ]

    #     print(exec_commands_on_remote_server(
    #         alma_conf["hostname"],
    #         alma_conf["username"],
    #         alma_conf["password"],
    #         postgres_commands_install,
    #     ))
