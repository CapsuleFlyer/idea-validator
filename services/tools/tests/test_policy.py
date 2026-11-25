import unittest

from src.policy import check_url, parse_allow_list

ALLOWED = parse_allow_list("api.github.com, hacker-news.firebaseio.com")


class PolicyTests(unittest.TestCase):
    def ok(self, url):
        return check_url(url, ALLOWED)[0]

    def test_allowed_host(self):
        self.assertTrue(self.ok("https://api.github.com/search/repositories?q=x"))

    def test_subdomain_of_allowed(self):
        self.assertTrue(self.ok("https://v2.api.github.com/x"))

    def test_lookalike_host_blocked(self):
        self.assertFalse(self.ok("https://evilapi.github.com.attacker.io/"))
        self.assertFalse(self.ok("https://notapi.github.com.example/"))

    def test_http_blocked(self):
        self.assertFalse(self.ok("http://api.github.com/"))

    def test_ip_literals_blocked(self):
        self.assertFalse(self.ok("https://169.254.169.254/latest/meta-data"))
        self.assertFalse(self.ok("https://127.0.0.1/"))

    def test_credentials_blocked(self):
        self.assertFalse(self.ok("https://user:pw@api.github.com/"))

    def test_odd_port_blocked(self):
        self.assertFalse(self.ok("https://api.github.com:8443/"))

    def test_garbage_blocked(self):
        self.assertFalse(self.ok("not a url"))
        self.assertFalse(self.ok(""))


if __name__ == "__main__":
    unittest.main()
