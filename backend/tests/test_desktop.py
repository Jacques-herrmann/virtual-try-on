import socket

from vto import desktop


def test_find_free_port_is_bindable():
    port = desktop.find_free_port()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


def test_login_url():
    assert desktop.login_url(5000, "abc") == "http://127.0.0.1:5000/api/session?token=abc"
