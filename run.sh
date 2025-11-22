#!/bin/bash
# Quick start script for Discord Research Assistant

set -e

echo "Discord Research Assistant - Quick Start"
echo "========================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Please copy .env.example to .env and configure it"
    echo "  cp .env.example .env"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running"
    echo "Please start Docker and try again"
    exit 1
fi

echo ""
echo "Starting services with Docker Compose..."
docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 5

echo ""
echo "Checking service status..."
docker-compose ps

echo ""
echo "Bot logs (Ctrl+C to exit):"
echo "========================================"
docker-compose logs -f bot
