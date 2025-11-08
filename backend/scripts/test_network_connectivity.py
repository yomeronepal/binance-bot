#!/usr/bin/env python3
"""
Network Connectivity Diagnostic Script

Tests connectivity to Binance API and diagnoses common network issues.
Run this inside Docker container:
    docker exec binancebot_web python backend/scripts/test_network_connectivity.py
"""
import asyncio
import socket
import sys
import time
from typing import List, Tuple

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}{text.center(80)}{RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}❌ {text}{RESET}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠️  {text}{RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{BLUE}ℹ️  {text}{RESET}")


async def test_dns_resolution() -> Tuple[bool, str]:
    """Test DNS resolution for api.binance.com."""
    print_info("Testing DNS resolution for api.binance.com...")
    try:
        host = "api.binance.com"
        loop = asyncio.get_event_loop()
        addresses = await loop.getaddrinfo(host, 443, family=socket.AF_UNSPEC)

        if addresses:
            ips = [addr[4][0] for addr in addresses]
            unique_ips = list(set(ips))
            print_success(f"DNS resolution successful: {', '.join(unique_ips)}")
            return True, f"Resolved to {len(unique_ips)} IP(s)"
        else:
            print_error("DNS resolution returned no addresses")
            return False, "No addresses returned"
    except socket.gaierror as e:
        print_error(f"DNS resolution failed: {e}")
        return False, str(e)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False, str(e)


async def test_ping_google_dns() -> Tuple[bool, str]:
    """Test connectivity to Google DNS (8.8.8.8)."""
    print_info("Testing connectivity to Google DNS (8.8.8.8:53)...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('8.8.8.8', 53))
        sock.close()

        if result == 0:
            print_success("Can reach Google DNS")
            return True, "Reachable"
        else:
            print_error(f"Cannot reach Google DNS (error code: {result})")
            return False, f"Error code {result}"
    except Exception as e:
        print_error(f"Failed to test Google DNS: {e}")
        return False, str(e)


async def test_http_connection() -> Tuple[bool, str]:
    """Test HTTP connection to Binance API."""
    print_info("Testing HTTP connection to api.binance.com...")
    try:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        connector = aiohttp.TCPConnector(ssl=True)

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            start_time = time.time()
            async with session.get('https://api.binance.com/api/v3/ping') as response:
                elapsed = time.time() - start_time
                if response.status == 200:
                    print_success(f"HTTP connection successful (latency: {elapsed * 1000:.0f}ms)")
                    return True, f"{elapsed * 1000:.0f}ms latency"
                else:
                    print_error(f"HTTP connection returned status {response.status}")
                    return False, f"Status {response.status}"
    except aiohttp.ClientConnectorError as e:
        print_error(f"Connection error: {e}")
        return False, str(e)
    except asyncio.TimeoutError:
        print_error("Connection timed out")
        return False, "Timeout"
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False, str(e)


async def test_api_endpoint() -> Tuple[bool, str]:
    """Test actual Binance API endpoint."""
    print_info("Testing Binance API /api/v3/exchangeInfo endpoint...")
    try:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            start_time = time.time()
            async with session.get('https://api.binance.com/api/v3/exchangeInfo') as response:
                elapsed = time.time() - start_time
                if response.status == 200:
                    data = await response.json()
                    symbols = len(data.get('symbols', []))
                    print_success(
                        f"API endpoint working (latency: {elapsed * 1000:.0f}ms, {symbols} symbols)"
                    )
                    return True, f"{symbols} symbols loaded"
                else:
                    print_error(f"API returned status {response.status}")
                    return False, f"Status {response.status}"
    except Exception as e:
        print_error(f"API test failed: {e}")
        return False, str(e)


async def test_docker_network() -> Tuple[bool, str]:
    """Test Docker network configuration."""
    print_info("Checking Docker network configuration...")
    try:
        # Try to read /etc/resolv.conf to check DNS servers
        with open('/etc/resolv.conf', 'r') as f:
            content = f.read()
            nameservers = [
                line.split()[1] for line in content.split('\n')
                if line.startswith('nameserver')
            ]

        if nameservers:
            print_success(f"Docker DNS servers: {', '.join(nameservers)}")
            return True, f"{len(nameservers)} DNS server(s)"
        else:
            print_warning("No DNS servers configured in Docker")
            return False, "No DNS servers"
    except FileNotFoundError:
        print_warning("Not running in Docker or /etc/resolv.conf not found")
        return True, "Non-Docker environment"
    except Exception as e:
        print_error(f"Failed to check Docker network: {e}")
        return False, str(e)


async def run_all_tests():
    """Run all connectivity tests."""
    print_header("NETWORK CONNECTIVITY DIAGNOSTIC")

    print(f"{BLUE}Running comprehensive network tests...{RESET}\n")

    results = {}

    # Test 1: Docker Network
    print_header("Test 1: Docker Network Configuration")
    results['docker'] = await test_docker_network()

    # Test 2: Basic Connectivity (Google DNS)
    print_header("Test 2: Basic Internet Connectivity")
    results['internet'] = await test_ping_google_dns()

    # Test 3: DNS Resolution
    print_header("Test 3: DNS Resolution")
    results['dns'] = await test_dns_resolution()

    # Test 4: HTTP Connection
    print_header("Test 4: HTTP Connection")
    results['http'] = await test_http_connection()

    # Test 5: API Endpoint
    print_header("Test 5: Binance API Endpoint")
    results['api'] = await test_api_endpoint()

    # Summary
    print_header("DIAGNOSTIC SUMMARY")

    passed = sum(1 for status, _ in results.values() if status)
    total = len(results)

    print(f"\nTests Passed: {passed}/{total}\n")

    for test_name, (status, detail) in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {test_name.upper():15} - {detail}")

    # Recommendations
    print_header("RECOMMENDATIONS")

    if not results['internet'][0]:
        print_error(
            "Cannot reach the internet. Check:\n"
            "  1. Docker host has internet connection\n"
            "  2. Docker network mode is correct\n"
            "  3. VPN/firewall not blocking outbound connections"
        )
    elif not results['dns'][0]:
        print_error(
            "DNS resolution failing. Solutions:\n"
            "  1. Check Docker DNS settings in /etc/resolv.conf\n"
            "  2. Try: docker-compose down && docker-compose up -d\n"
            "  3. Add DNS servers to docker-compose.yml:\n"
            "     dns:\n"
            "       - 8.8.8.8\n"
            "       - 8.8.4.4"
        )
    elif not results['http'][0]:
        print_error(
            "HTTP connection failing. Check:\n"
            "  1. Firewall blocking HTTPS (port 443)\n"
            "  2. SSL certificate issues\n"
            "  3. Proxy configuration needed"
        )
    elif not results['api'][0]:
        print_error(
            "Binance API not responding. Check:\n"
            "  1. Binance API status: https://www.binance.com/en/support/announcement\n"
            "  2. Your IP might be rate limited or blocked\n"
            "  3. Try again in a few minutes"
        )
    else:
        print_success(
            "All tests passed! Binance API is reachable.\n"
            "If you're still having issues, check application logs."
        )

    print()
    return passed == total


async def main():
    """Main entry point."""
    try:
        success = await run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Test interrupted by user{RESET}")
        sys.exit(130)
    except Exception as e:
        print_error(f"Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
