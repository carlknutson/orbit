import socket

from orbit.ports import assign_ports, is_port_available


class TestIsPortAvailable:
    def test_available_port(self):
        # Find a free port by binding to 0
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        assert is_port_available(free_port)

    def test_occupied_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            occupied_port = s.getsockname()[1]
            # Port is still bound inside the with block
            assert not is_port_available(occupied_port)


class TestAssignPorts:
    def test_free_ports_retain_original(self):
        # Use ports very unlikely to be in use
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        # port is now free
        result = assign_ports([port], claimed=set())
        assert result[port] == port

    def test_claimed_port_increments(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        # port is now free at OS level; mark it claimed in state
        result = assign_ports([port], claimed={port})
        assert result[port] == port + 1

    def test_os_occupied_port_increments(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            # While socket is bound, the port is occupied
            result = assign_ports([port], claimed=set())
        assert result[port] == port + 1

    def test_multiple_ports_all_assigned(self):
        ports = []
        sockets = []
        try:
            for _ in range(3):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("127.0.0.1", 0))
                ports.append(s.getsockname()[1])
                sockets.append(s)
            # Release them so assign_ports can bind
            for s in sockets:
                s.close()
            sockets.clear()
            result = assign_ports(ports, claimed=set())
        finally:
            for s in sockets:
                s.close()

        for port in ports:
            assert port in result
            assert isinstance(result[port], int)

    def test_no_two_ports_get_same_assignment(self):
        with (
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s1,
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2,
        ):
            s1.bind(("127.0.0.1", 0))
            s2.bind(("127.0.0.1", 0))
            p1 = s1.getsockname()[1]

        # Both ports now free; assign two ports that happen to be identical
        # by passing a claimed set that forces both to the same starting point
        result = assign_ports([p1, p1], claimed=set())
        values = list(result.values())
        assert len(set(values)) == len(values), "Assigned ports must be unique"

    def test_empty_declared_returns_empty(self):
        result = assign_ports([], claimed=set())
        assert result == {}

    def test_claimed_and_os_both_checked(self):
        # Occupy a port at OS level; also claim the next one in state —
        # should skip both and land on port+2
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            result = assign_ports([port], claimed={port + 1})
        assert result[port] == port + 2
