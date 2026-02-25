FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://nixos.org/nix/install -o /tmp/install-nix.sh \
    && sh /tmp/install-nix.sh --daemon --yes \
    && rm -f /tmp/install-nix.sh

RUN mkdir -p /etc/nix \
    && printf "experimental-features = nix-command flakes\n" >> /etc/nix/nix.conf

RUN . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh \
    && nix profile install --profile /nix/var/nix/profiles/default github:NixOS/nixpkgs/nixos-unstable#codex \
    && ln -sf /nix/var/nix/profiles/default/bin/codex /usr/local/bin/codex
