# Local Directory Server

A threaded HTTP/HTTPS server that exposes local Google Drive content as a JSON API for fast LAN-based file access in classrooms.

## Why This Exists

### The Problem
Classrooms need to access large presentation files (PPSX, PPTX, videos) from Google Drive. Downloading these files over the internet every time is slow and unreliable, especially with 30+ students accessing content simultaneously.

### The Solution
1. **Local caching**: Google Drive syncs files to a local Windows machine at the school
2. **LAN server**: This Python server exposes those files over the local network
3. **Fast access**: Classroom tablets/laptops fetch files from the LAN server instead of the internet

## Why a Subdomain Pointing to a LAN IP?

Modern browsers enforce strict security policies. The main application runs on `https://erp.walnutedu.in`, and browsers block requests from HTTPS pages to:
- Plain HTTP servers (`http://192.168.1.100:8050`) - **blocked** (mixed content)
- IP addresses with self-signed certs - **blocked** (certificate errors)

### The Solution: Subdomain + Real SSL Certificate

1. **Create a subdomain** in GoDaddy DNS: `shivanelocal.walnutedu.in`
2. **Point it to the LAN IP**: `192.168.x.x` (the local server's IP on the school network)
3. **Get a real SSL certificate** from Let's Encrypt for the subdomain
4. **Run the server with HTTPS** using that certificate

This way:
- Browser sees a valid domain with a trusted SSL cert
- No mixed content warnings
- No certificate errors
- Works seamlessly from `https://erp.walnutedu.in`

## Setup Instructions

### 1. Install Python Dependencies

The server uses only Python standard library - no pip packages needed.

### 2. DNS Setup (GoDaddy)

1. Log into GoDaddy DNS management for `walnutedu.in`
2. Add an A record:
   - **Name**: `shivanelocal` (or `wakadlocal`, `fursungilocal` for other schools)
   - **Type**: A
   - **Value**: The LAN IP of the server (e.g., `192.168.1.100`)
   - **TTL**: 1 hour

> **Note**: This DNS record points to a private/LAN IP address. It will only resolve correctly when accessed from within the school network.

### 3. SSL Certificate Setup (Certbot)

Since the server is on a LAN IP (not publicly accessible), you must use **DNS-01 challenge** to verify domain ownership.

#### Install Certbot on Windows

```powershell
# Download and install Certbot from https://certbot.eff.org/
# Or use winget:
winget install EFF.Certbot
```

#### Obtain Certificate with DNS Challenge

```powershell
certbot certonly --manual --preferred-challenges dns -d shivanelocal.walnutedu.in
```

Certbot will ask you to create a TXT record:
1. Go to GoDaddy DNS
2. Add a TXT record:
   - **Name**: `_acme-challenge.shivanelocal`
   - **Type**: TXT
   - **Value**: (the value certbot provides)
3. Wait 1-2 minutes for DNS propagation
4. Press Enter in certbot to continue

Certificates will be saved to:
```
C:\Certbot\live\shivanelocal.walnutedu.in\fullchain.pem
C:\Certbot\live\shivanelocal.walnutedu.in\privkey.pem
```

### 4. Running the Server

```powershell
# Basic HTTP (not recommended for production)
python directory_server.py -p 8050 -d "G:\My Drive\Content"

# With HTTPS (recommended)
python directory_server.py -p 8050 -d "G:\My Drive\Content" --cert "C:\Certbot\live\shivanelocal.walnutedu.in\fullchain.pem" --key "C:\Certbot\live\shivanelocal.walnutedu.in\privkey.pem"
```

### 5. Run as Windows Service (Optional)

To run the server automatically on startup, create a Windows Task Scheduler task or use NSSM (Non-Sucking Service Manager).

## API Endpoints

### List Directory
```
GET https://shivanelocal.walnutedu.in:8050/path/to/directory/
```

Returns JSON:
```json
{
  "directory": "/path/to/directory/",
  "total_items": 5,
  "generated_at": "2025-01-30T10:00:00",
  "files": [
    {
      "name": "presentation.ppsx",
      "extension": "ppsx",
      "type": "file",
      "size_bytes": 2299529,
      "modified_timestamp": 1749023167.513,
      "modified_iso": "2025-06-04T13:16:07",
      "path": "/path/to/directory/presentation.ppsx"
    }
  ]
}
```

### Download File
```
GET https://shivanelocal.walnutedu.in:8050/path/to/file.ppsx
```

Returns the file with appropriate MIME type and Content-Disposition headers.

## Certificate Renewal

Let's Encrypt certificates expire every 90 days. To renew:

```powershell
certbot renew
```

For automatic renewal, add a Windows Task Scheduler task to run `certbot renew` daily.

## Concurrency

The server uses `ThreadingMixIn` to handle multiple concurrent requests. Each incoming request spawns a new thread, allowing 100+ simultaneous connections.

## Troubleshooting

### "Connection refused" from browser
- Ensure the server is running
- Check Windows Firewall allows the port (8050)
- Verify the DNS record points to the correct LAN IP

### "Certificate error" in browser
- Ensure you're using `--cert` and `--key` flags
- Verify certificate files exist and are readable
- Check certificate hasn't expired: `certbot certificates`

### "CORS error" in browser console
- The server includes CORS headers by default
- If issues persist, check browser dev tools for specific error

### Google Drive files not showing
- Ensure Google Drive is running and synced
- Check the `-d` directory path is correct
- Server waits for Google Drive process on startup (can skip with `--skip-drive-check`)

## License

MIT
