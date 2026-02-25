# Minimal ngIRCd setup for OpenClaw

## 1) Prepare config

Use `irc/ngircd.conf` as your starting point.

```bash
mkdir -p /your/path/config
cp irc/ngircd.conf /your/path/config/ngircd.conf
```

## 2) Run ngIRCd

```bash
docker run -d \
  --name ngircd \
  -p 6667:6667 \
  -v /your/path/config:/config \
  --restart unless-stopped \
  lscr.io/linuxserver/ngircd:latest
```

## 3) OpenClaw connection values

For OpenClaw IRC settings, use:

- host: `127.0.0.1` (or `ngircd` if OpenClaw runs in the same Docker network)
- port: `6667`
- tls/ssl: `false`
- channel: `#openclaw`
- nick: any unique nickname

If OpenClaw and ngIRCd are both in Docker, put them on the same user-defined network and use `ngircd` as the host.
