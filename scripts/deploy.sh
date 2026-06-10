#!/bin/bash
set -e
echo "军鸽云链 AI 网关 - Phase 1 部署"
echo "================================"

HOST=${1:-}
if [ -z "$HOST" ]; then
    echo "用法: ./deploy.sh <tokyo|guangzhou>"
    exit 1
fi

scp -r . root@$HOST:/opt/ai-gateway/
ssh root@$HOST "cd /opt/ai-gateway && docker-compose -f docker-compose.$HOST.yml up -d"
ssh root@$HOST "curl -s http://localhost:8081/health"
echo "部署完成: $HOST"
