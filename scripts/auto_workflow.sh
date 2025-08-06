#!/bin/bash
# 自动化工作流脚本

echo "==================================================="
echo "Newsletter Crawler 自动化工作流"
echo "==================================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 步骤1: 爬取文章
echo -e "${YELLOW}[步骤 1/5] 爬取所有文章...${NC}"
python3 main.py crawl --concurrent 5 --batch-size 10
if [ $? -ne 0 ]; then
    echo -e "${RED}爬取失败！${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 爬取完成${NC}"
echo ""

# 步骤2: 检查空内容
echo -e "${YELLOW}[步骤 2/5] 检查空内容文章...${NC}"
python3 main.py check
echo ""

# 步骤3: 询问是否重新爬取
read -p "是否重新爬取问题文章? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}[步骤 3/5] 删除并重新爬取问题文章...${NC}"
    
    # 先删除
    python3 main.py delete
    
    # 重新爬取
    python3 main.py recrawl
    echo -e "${GREEN}✓ 重新爬取完成${NC}"
else
    echo -e "${YELLOW}[步骤 3/5] 跳过重新爬取${NC}"
fi
echo ""

# 步骤4: 最终检查
echo -e "${YELLOW}[步骤 4/5] 最终内容检查...${NC}"
python3 main.py check
echo ""

# 步骤5: 询问是否上传到OSS
read -p "是否上传到OSS? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}[步骤 5/5] 上传到OSS...${NC}"
    python3 main.py upload
    echo -e "${GREEN}✓ 上传完成${NC}"
else
    echo -e "${YELLOW}[步骤 5/5] 跳过OSS上传${NC}"
fi

echo ""
echo -e "${GREEN}==================================================="
echo "工作流完成！"
echo "===================================================${NC}"