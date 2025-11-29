#!/bin/bash
#
# Health check script for Marxist Search Engine
# Usage: ./health_check.sh
#
# Checks the status of all services and provides a summary
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

API_URL="${API_URL:-http://localhost:8000}"

echo "========================================="
echo "Marxist Search Engine - Health Check"
echo "========================================="
echo ""

# Check API service
echo -e "${BLUE}Checking API service...${NC}"
if systemctl is-active --quiet marxist-search-api.service; then
    echo -e "  ${GREEN}✓${NC} API service is running"
else
    echo -e "  ${RED}✗${NC} API service is NOT running"
fi

# Check update timer
echo -e "${BLUE}Checking update timer...${NC}"
if systemctl is-active --quiet marxist-search-update.timer; then
    echo -e "  ${GREEN}✓${NC} Update timer is active"

    # Show next run time
    NEXT_RUN=$(systemctl status marxist-search-update.timer | grep "Trigger:" | awk '{print $2, $3, $4}')
    if [ -n "$NEXT_RUN" ]; then
        echo -e "  ${YELLOW}→${NC} Next update: $NEXT_RUN"
    fi
else
    echo -e "  ${RED}✗${NC} Update timer is NOT active"
fi

# Check API health endpoint
echo -e "${BLUE}Checking API health endpoint...${NC}"
HEALTH_RESPONSE=$(curl -s "$API_URL/api/v1/health" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} API is responding"

    # Parse response (requires jq)
    if command -v jq &> /dev/null; then
        INDEX_LOADED=$(echo "$HEALTH_RESPONSE" | jq -r '.index_loaded // "unknown"')
        DOC_COUNT=$(echo "$HEALTH_RESPONSE" | jq -r '.index_document_count // "unknown"')

        if [ "$INDEX_LOADED" = "true" ]; then
            echo -e "  ${GREEN}✓${NC} Index loaded ($DOC_COUNT documents)"
        else
            echo -e "  ${RED}✗${NC} Index NOT loaded"
        fi
    fi
else
    echo -e "  ${RED}✗${NC} API is NOT responding"
fi

# Check Nginx
echo -e "${BLUE}Checking Nginx...${NC}"
if systemctl is-active --quiet nginx; then
    echo -e "  ${GREEN}✓${NC} Nginx is running"

    # Test config
    if nginx -t 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Nginx configuration valid"
    else
        echo -e "  ${YELLOW}⚠${NC} Nginx configuration has issues"
    fi
else
    echo -e "  ${RED}✗${NC} Nginx is NOT running"
fi

# Check disk space
echo -e "${BLUE}Checking disk space...${NC}"
DATA_USAGE=$(df -h /var/lib/marxist-search 2>/dev/null | awk 'NR==2 {print $5}' | sed 's/%//')
if [ -n "$DATA_USAGE" ]; then
    if [ "$DATA_USAGE" -lt 80 ]; then
        echo -e "  ${GREEN}✓${NC} Disk usage: ${DATA_USAGE}%"
    elif [ "$DATA_USAGE" -lt 90 ]; then
        echo -e "  ${YELLOW}⚠${NC} Disk usage: ${DATA_USAGE}% (warning)"
    else
        echo -e "  ${RED}✗${NC} Disk usage: ${DATA_USAGE}% (critical)"
    fi
fi

# Check memory
echo -e "${BLUE}Checking memory...${NC}"
MEM_USAGE=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100)}')
if [ "$MEM_USAGE" -lt 80 ]; then
    echo -e "  ${GREEN}✓${NC} Memory usage: ${MEM_USAGE}%"
elif [ "$MEM_USAGE" -lt 90 ]; then
    echo -e "  ${YELLOW}⚠${NC} Memory usage: ${MEM_USAGE}% (warning)"
else
    echo -e "  ${RED}✗${NC} Memory usage: ${MEM_USAGE}% (critical)"
fi

# Check database
echo -e "${BLUE}Checking database...${NC}"
if [ -f "/var/lib/marxist-search/articles.db" ]; then
    DB_SIZE=$(du -h /var/lib/marxist-search/articles.db | awk '{print $1}')
    echo -e "  ${GREEN}✓${NC} Database exists ($DB_SIZE)"
else
    echo -e "  ${RED}✗${NC} Database NOT found"
fi

# Check index
echo -e "${BLUE}Checking search index...${NC}"
if [ -d "/var/lib/marxist-search/txtai" ]; then
    INDEX_SIZE=$(du -sh /var/lib/marxist-search/txtai 2>/dev/null | awk '{print $1}')
    echo -e "  ${GREEN}✓${NC} Index exists ($INDEX_SIZE)"
else
    echo -e "  ${RED}✗${NC} Index NOT found"
fi

# Recent errors
echo -e "${BLUE}Checking recent errors...${NC}"
if [ -f "/var/log/marxist-search/errors.log" ]; then
    ERROR_COUNT=$(tail -100 /var/log/marxist-search/errors.log 2>/dev/null | wc -l)
    if [ "$ERROR_COUNT" -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} No recent errors"
    else
        echo -e "  ${YELLOW}⚠${NC} $ERROR_COUNT errors in last 100 log lines"
    fi
fi

echo ""
echo "========================================="
echo "Health check complete"
echo "========================================="
echo ""
