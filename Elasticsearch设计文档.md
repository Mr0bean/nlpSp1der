# Elasticsearch Newsletter推荐系统设计文档

## 1. 系统概述

本文档描述了基于Elasticsearch构建的Newsletter文章推荐系统的技术架构设计。系统利用ES的全文搜索、向量检索和聚合分析能力，为用户提供个性化的文章推荐服务。

## 2. 数据结构分析

### 2.1 原始数据结构
基于爬虫输出的JSON数据，每篇文章包含以下核心字段：

```json
{
  "id": 169333505,                           // 文章唯一标识
  "title": "🥇Top AI Papers of the Week",    // 标题
  "subtitle": "The Top AI Papers...",        // 副标题
  "description": "The Top AI Papers...",     // 描述
  "post_date": "2025-07-27T14:52:20.585Z",  // 发布时间
  "type": "newsletter",                      // 类型：newsletter/tutorial/paper
  "wordcount": 2403,                         // 字数
  "canonical_url": "https://...",           // 原始URL
  "slug": "top-ai-papers-of-the-week-cf2",  // URL slug
  "reactions": {"❤": 35},                   // 用户反应
  "audience": "everyone",                    // 受众：everyone/only_paid
  "postTags": [                             // 标签列表
    {
      "id": "aeac318f-b983-41c9-87b7-13c8a81dc8e6",
      "name": "AI Papers of the Week",
      "slug": "ai"
    }
  ],
  "cover_image": {...},                     // 封面图片
  "local_images": [...],                    // 内容图片列表
  "content_hash": "8cbed07034b7e42d...",   // 内容哈希
  "processed_date": "2025-08-07T00:14:52"   // 处理时间
}
```

## 3. Elasticsearch索引设计

### 3.1 主索引：newsletter_articles

```json
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "english_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": [
            "lowercase",
            "english_stop",
            "english_stemmer",
            "synonym_filter"
          ]
        },
        "tag_analyzer": {
          "type": "custom",
          "tokenizer": "keyword",
          "filter": ["lowercase"]
        },
        "ngram_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": [
            "lowercase",
            "ngram_filter"
          ]
        }
      },
      "filter": {
        "english_stop": {
          "type": "stop",
          "stopwords": "_english_"
        },
        "english_stemmer": {
          "type": "stemmer",
          "language": "english"
        },
        "synonym_filter": {
          "type": "synonym",
          "synonyms": [
            "ai,artificial intelligence",
            "ml,machine learning",
            "llm,large language model",
            "nlp,natural language processing"
          ]
        },
        "ngram_filter": {
          "type": "ngram",
          "min_gram": 2,
          "max_gram": 3
        }
      }
    }
  },
  "mappings": {
    "properties": {
      // 基础字段
      "id": {
        "type": "long"
      },
      "title": {
        "type": "text",
        "analyzer": "english_analyzer",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          },
          "ngram": {
            "type": "text",
            "analyzer": "ngram_analyzer"
          }
        }
      },
      "subtitle": {
        "type": "text",
        "analyzer": "english_analyzer"
      },
      "description": {
        "type": "text",
        "analyzer": "english_analyzer"
      },
      
      // 内容字段
      "content": {
        "type": "text",
        "analyzer": "english_analyzer",
        "term_vector": "with_positions_offsets"
      },
      "content_embedding": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine"
      },
      
      // 时间字段
      "post_date": {
        "type": "date"
      },
      "processed_date": {
        "type": "date"
      },
      
      // 分类字段
      "type": {
        "type": "keyword"
      },
      "audience": {
        "type": "keyword"
      },
      
      // 标签字段
      "tags": {
        "type": "nested",
        "properties": {
          "id": {
            "type": "keyword"
          },
          "name": {
            "type": "text",
            "analyzer": "english_analyzer",
            "fields": {
              "keyword": {
                "type": "keyword"
              }
            }
          },
          "slug": {
            "type": "keyword"
          }
        }
      },
      
      // 统计字段
      "wordcount": {
        "type": "integer"
      },
      "reaction_count": {
        "type": "integer"
      },
      "reactions": {
        "type": "object",
        "enabled": false
      },
      
      // URL字段
      "canonical_url": {
        "type": "keyword"
      },
      "slug": {
        "type": "keyword"
      },
      
      // 图片字段
      "cover_image_path": {
        "type": "keyword"
      },
      "image_count": {
        "type": "integer"
      },
      
      // 哈希字段
      "content_hash": {
        "type": "keyword"
      },
      
      // 推荐相关字段
      "popularity_score": {
        "type": "float"
      },
      "quality_score": {
        "type": "float"
      },
      "freshness_score": {
        "type": "float"
      },
      "combined_score": {
        "type": "float"
      }
    }
  }
}
```

### 3.2 辅助索引：user_interactions

```json
{
  "mappings": {
    "properties": {
      "user_id": {
        "type": "keyword"
      },
      "article_id": {
        "type": "long"
      },
      "interaction_type": {
        "type": "keyword"  // view, like, share, bookmark
      },
      "interaction_time": {
        "type": "date"
      },
      "duration": {
        "type": "integer"  // 阅读时长（秒）
      },
      "scroll_depth": {
        "type": "float"    // 滚动深度（0-1）
      }
    }
  }
}
```

### 3.3 辅助索引：user_profiles

```json
{
  "mappings": {
    "properties": {
      "user_id": {
        "type": "keyword"
      },
      "preferred_tags": {
        "type": "keyword"
      },
      "reading_history": {
        "type": "long"
      },
      "preference_embedding": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine"
      },
      "avg_reading_time": {
        "type": "float"
      },
      "preferred_wordcount_range": {
        "properties": {
          "min": {"type": "integer"},
          "max": {"type": "integer"}
        }
      }
    }
  }
}
```

## 4. 数据处理Pipeline

### 4.1 Ingest Pipeline配置

```json
{
  "description": "Newsletter article processing pipeline",
  "processors": [
    {
      "script": {
        "lang": "painless",
        "source": """
          // 计算reaction总数
          int total = 0;
          if (ctx.reactions != null) {
            for (entry in ctx.reactions.entrySet()) {
              total += entry.getValue();
            }
          }
          ctx.reaction_count = total;
          
          // 计算图片数量
          if (ctx.local_images != null) {
            ctx.image_count = ctx.local_images.size();
          } else {
            ctx.image_count = 0;
          }
          
          // 提取封面图片路径
          if (ctx.cover_image != null && ctx.cover_image.path != null) {
            ctx.cover_image_path = ctx.cover_image.path;
          }
          
          // 重命名tags字段
          if (ctx.postTags != null) {
            ctx.tags = ctx.postTags;
            ctx.remove('postTags');
          }
        """
      }
    },
    {
      "script": {
        "lang": "painless",
        "source": """
          // 计算popularity_score
          float score = 0.0;
          
          // 基于反应数
          score += ctx.reaction_count * 0.3;
          
          // 基于字数（最优范围300-2000）
          if (ctx.wordcount >= 300 && ctx.wordcount <= 2000) {
            score += 10;
          } else if (ctx.wordcount > 2000) {
            score += 5;
          }
          
          // 基于时间衰减
          long now = System.currentTimeMillis();
          long postTime = ZonedDateTime.parse(ctx.post_date).toInstant().toEpochMilli();
          long daysDiff = (now - postTime) / (1000 * 60 * 60 * 24);
          
          if (daysDiff <= 7) {
            score += 20;
          } else if (daysDiff <= 30) {
            score += 10;
          } else if (daysDiff <= 90) {
            score += 5;
          }
          
          // 基于类型
          if (ctx.type == 'newsletter') {
            score += 5;
          }
          
          ctx.popularity_score = score;
          
          // 计算freshness_score
          ctx.freshness_score = Math.max(0, 100 - daysDiff * 0.5);
        """
      }
    },
    {
      "inference": {
        "model_id": "sentence-transformers__all-minilm-l6-v2",
        "target_field": "content_embedding",
        "field_map": {
          "title": "text_field"
        },
        "on_failure": [
          {
            "set": {
              "field": "_index",
              "value": "failed-{{{_index}}}"
            }
          }
        ]
      }
    }
  ]
}
```

### 4.2 向量化处理说明

使用Sentence Transformers模型（如all-MiniLM-L6-v2）生成384维向量：
- 输入：标题 + 副标题 + 描述的拼接文本
- 输出：384维稠密向量
- 用途：语义相似度匹配

## 5. 推荐查询模板

### 5.1 基于内容的推荐

```json
{
  "size": 10,
  "query": {
    "script_score": {
      "query": {
        "bool": {
          "must": [
            {
              "range": {
                "post_date": {
                  "gte": "now-90d"
                }
              }
            }
          ],
          "must_not": [
            {
              "terms": {
                "id": [/* 已读文章ID列表 */]
              }
            }
          ]
        }
      },
      "script": {
        "source": """
          double vector_score = cosineSimilarity(params.query_vector, 'content_embedding') + 1.0;
          double popularity = doc['popularity_score'].value / 100.0;
          double freshness = doc['freshness_score'].value / 100.0;
          
          return vector_score * 0.5 + popularity * 0.3 + freshness * 0.2;
        """,
        "params": {
          "query_vector": [/* 用户兴趣向量 */]
        }
      }
    }
  }
}
```

### 5.2 基于标签的推荐

```json
{
  "size": 10,
  "query": {
    "bool": {
      "should": [
        {
          "nested": {
            "path": "tags",
            "query": {
              "terms": {
                "tags.slug": ["ai", "machine-learning", "nlp"]
              }
            },
            "score_mode": "sum"
          }
        }
      ],
      "must": [
        {
          "range": {
            "post_date": {
              "gte": "now-30d"
            }
          }
        }
      ]
    }
  },
  "sort": [
    {
      "_score": {
        "order": "desc"
      }
    },
    {
      "popularity_score": {
        "order": "desc"
      }
    }
  ]
}
```

### 5.3 混合推荐（向量+关键词）

```json
{
  "size": 10,
  "query": {
    "bool": {
      "should": [
        {
          "script_score": {
            "query": {
              "match_all": {}
            },
            "script": {
              "source": "cosineSimilarity(params.query_vector, 'content_embedding') + 1.0",
              "params": {
                "query_vector": [/* 查询向量 */]
              }
            },
            "boost": 0.5
          }
        },
        {
          "multi_match": {
            "query": "large language models GPT",
            "fields": ["title^3", "subtitle^2", "description", "content"],
            "type": "best_fields",
            "boost": 0.3
          }
        },
        {
          "nested": {
            "path": "tags",
            "query": {
              "match": {
                "tags.name": "AI Papers"
              }
            },
            "boost": 0.2
          }
        }
      ]
    }
  },
  "rescore": {
    "window_size": 50,
    "query": {
      "rescore_query": {
        "function_score": {
          "functions": [
            {
              "gauss": {
                "post_date": {
                  "origin": "now",
                  "scale": "7d",
                  "decay": 0.5
                }
              }
            }
          ]
        }
      },
      "query_weight": 0.7,
      "rescore_query_weight": 0.3
    }
  }
}
```

### 5.4 热门文章查询

```json
{
  "size": 10,
  "query": {
    "function_score": {
      "query": {
        "range": {
          "post_date": {
            "gte": "now-7d"
          }
        }
      },
      "functions": [
        {
          "field_value_factor": {
            "field": "reaction_count",
            "factor": 1.2,
            "modifier": "log1p"
          }
        },
        {
          "gauss": {
            "post_date": {
              "origin": "now",
              "scale": "3d",
              "decay": 0.5
            }
          }
        }
      ],
      "score_mode": "sum",
      "boost_mode": "multiply"
    }
  },
  "sort": [
    {
      "_score": {
        "order": "desc"
      }
    }
  ]
}
```

### 5.5 相似文章查询（More Like This）

```json
{
  "size": 5,
  "query": {
    "more_like_this": {
      "fields": ["title", "subtitle", "description", "content"],
      "like": [
        {
          "_index": "newsletter_articles",
          "_id": "169333505"
        }
      ],
      "min_term_freq": 1,
      "max_query_terms": 25,
      "min_doc_freq": 2,
      "boost_terms": 1,
      "include": false
    }
  }
}
```

## 6. 聚合分析查询

### 6.1 标签热度分析

```json
{
  "size": 0,
  "aggs": {
    "popular_tags": {
      "nested": {
        "path": "tags"
      },
      "aggs": {
        "tag_counts": {
          "terms": {
            "field": "tags.slug",
            "size": 20
          },
          "aggs": {
            "tag_details": {
              "top_hits": {
                "size": 1,
                "_source": ["tags.name"]
              }
            },
            "avg_reactions": {
              "reverse_nested": {},
              "aggs": {
                "avg_count": {
                  "avg": {
                    "field": "reaction_count"
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### 6.2 时间趋势分析

```json
{
  "size": 0,
  "aggs": {
    "articles_over_time": {
      "date_histogram": {
        "field": "post_date",
        "calendar_interval": "week",
        "min_doc_count": 0
      },
      "aggs": {
        "article_types": {
          "terms": {
            "field": "type"
          }
        },
        "avg_wordcount": {
          "avg": {
            "field": "wordcount"
          }
        },
        "total_reactions": {
          "sum": {
            "field": "reaction_count"
          }
        }
      }
    }
  }
}
```

## 7. 数据导入脚本

### 7.1 Python导入示例

```python
from elasticsearch import Elasticsearch, helpers
import json
import hashlib
from datetime import datetime
import numpy as np

# 初始化ES客户端
es = Elasticsearch(
    ['http://localhost:9200'],
    http_auth=('elastic', 'password')
)

# 创建索引
def create_index():
    with open('index_mapping.json', 'r') as f:
        mapping = json.load(f)
    
    if es.indices.exists(index='newsletter_articles'):
        es.indices.delete(index='newsletter_articles')
    
    es.indices.create(index='newsletter_articles', body=mapping)

# 批量导入数据
def bulk_import_articles(articles_dir):
    actions = []
    
    for article_file in Path(articles_dir).glob('*/metadata.json'):
        with open(article_file, 'r') as f:
            article = json.load(f)
        
        # 读取Markdown内容
        md_file = article_file.parent / 'content.md'
        if md_file.exists():
            with open(md_file, 'r') as f:
                article['content'] = f.read()
        
        # 准备ES文档
        doc = {
            '_index': 'newsletter_articles',
            '_id': article['id'],
            '_source': article
        }
        
        actions.append(doc)
        
        # 每100条批量导入一次
        if len(actions) >= 100:
            helpers.bulk(es, actions)
            actions = []
    
    # 导入剩余数据
    if actions:
        helpers.bulk(es, actions)

# 生成向量（示例，实际需要使用模型）
def generate_embedding(text):
    # 这里应该调用实际的向量化模型
    # 示例：使用sentence-transformers
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embedding = model.encode(text)
    return embedding.tolist()

# 更新文档向量
def update_embeddings():
    # 获取所有文档
    response = es.search(
        index='newsletter_articles',
        body={'query': {'match_all': {}}, 'size': 1000}
    )
    
    for hit in response['hits']['hits']:
        doc = hit['_source']
        text = f"{doc.get('title', '')} {doc.get('subtitle', '')} {doc.get('description', '')}"
        
        embedding = generate_embedding(text)
        
        # 更新文档
        es.update(
            index='newsletter_articles',
            id=hit['_id'],
            body={'doc': {'content_embedding': embedding}}
        )

if __name__ == '__main__':
    create_index()
    bulk_import_articles('crawled_data/articles')
    update_embeddings()
```

## 8. 性能优化建议

### 8.1 索引优化
- **分片策略**：根据数据量调整，建议每个分片20-40GB
- **副本数量**：生产环境至少1个副本
- **刷新间隔**：批量导入时设置为-1，完成后恢复为1s

### 8.2 查询优化
- **使用filter代替query**：对于精确匹配字段
- **缓存策略**：启用查询缓存和请求缓存
- **分页优化**：使用search_after代替from/size

### 8.3 向量检索优化
- **HNSW参数调优**：
  ```json
  "index.knn": true,
  "index.knn.algo_param.ef_search": 100,
  "index.knn.algo_param.ef_construction": 200,
  "index.knn.algo_param.m": 16
  ```

## 9. 监控指标

### 9.1 关键指标
- **索引速率**：documents/second
- **查询延迟**：p50, p95, p99
- **缓存命中率**：query cache, request cache
- **CPU/内存使用率**

### 9.2 推荐质量指标
- **点击率（CTR）**：推荐文章的点击比例
- **停留时长**：用户阅读时间
- **完读率**：滚动到底部的比例
- **互动率**：点赞、分享等行为

## 10. 部署架构

### 10.1 集群配置（生产环境）
```yaml
# 3个主节点
master_nodes:
  - node1: 
      heap: 4GB
      cpu: 2
      role: master
  
# 3个数据节点  
data_nodes:
  - node2:
      heap: 16GB
      cpu: 8
      role: data
      storage: 500GB SSD
  
# 2个协调节点
coordinating_nodes:
  - node3:
      heap: 8GB
      cpu: 4
      role: ingest
```

### 10.2 备份策略
- **快照频率**：每日增量，每周全量
- **保留策略**：30天滚动
- **存储位置**：S3/MinIO

## 11. API接口设计

### 11.1 推荐接口
```python
# GET /api/recommendations
{
  "user_id": "user123",
  "size": 10,
  "strategy": "hybrid",  # content, collaborative, hybrid
  "filters": {
    "type": ["newsletter"],
    "min_date": "2025-01-01"
  }
}
```

### 11.2 搜索接口
```python
# GET /api/search
{
  "query": "machine learning",
  "size": 20,
  "from": 0,
  "filters": {
    "tags": ["ai", "ml"]
  },
  "sort": "relevance"  # relevance, date, popularity
}
```

## 12. 总结

本设计充分利用Elasticsearch的以下能力：
1. **全文搜索**：多语言分析器、同义词、N-gram
2. **向量检索**：384维稠密向量的语义匹配
3. **混合检索**：结合关键词和向量的混合评分
4. **实时聚合**：标签热度、时间趋势分析
5. **个性化推荐**：基于用户行为的动态推荐

系统可根据实际需求进行扩展，如增加用户画像、协同过滤等高级推荐算法。