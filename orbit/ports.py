import socket


def is_port_available(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def assign_ports(
    declared: list[int],
    claimed: set[int],
) -> dict[int, int]:
    assigned: dict[int, int] = {}
    in_use = set(claimed)

    for port in declared:
        candidate = port
        while candidate in in_use or not is_port_available(candidate):
            candidate += 1
        assigned[port] = candidate
        in_use.add(candidate)

    return assigned
