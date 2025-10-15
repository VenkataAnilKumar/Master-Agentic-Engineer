# Week 1: Agent Foundations & LLM Orchestration

## 🎯 Learning Objectives

By the end of this week, you will:

- **Understand** core agent architectures and design patterns
- **Master** LLM orchestration and prompt engineering techniques
- **Implement** containerized agent deployments with Docker
- **Set up** comprehensive development environment and tooling
- **Build** a production-ready research agent with observability

## 📚 Theory & Concepts

### Agent Architecture Fundamentals

#### Core Components
1. **Reasoning Engine**: The cognitive core that processes information and makes decisions
2. **Memory System**: Short-term and long-term memory for context and learning
3. **Tool Interface**: Integration layer for external APIs and functions
4. **Execution Engine**: Task orchestration and workflow management
5. **Observability Layer**: Monitoring, logging, and metrics collection

#### Design Patterns
- **ReAct (Reasoning + Acting)**: Interleave reasoning and action steps
- **Chain-of-Thought**: Sequential reasoning with explicit thought processes
- **Tool-Use**: Function calling and external API integration
- **Memory-Augmented**: Persistent context and knowledge retrieval

### LLM Orchestration Strategies

#### Model Selection Criteria
- **Task Complexity**: Match model capability to task requirements
- **Latency Requirements**: Balance accuracy vs response time
- **Cost Optimization**: Consider token usage and pricing models
- **Reliability**: Model availability and error handling

#### Prompt Engineering Best Practices
- **Clear Instructions**: Specific, unambiguous task descriptions
- **Context Management**: Efficient use of context window
- **Output Formatting**: Structured responses for parsing
- **Error Handling**: Graceful degradation strategies

### Containerization for AI Agents

#### Benefits
- **Reproducibility**: Consistent environments across deployments
- **Scalability**: Easy horizontal scaling and load distribution
- **Isolation**: Secure sandboxing and resource management
- **Portability**: Deploy anywhere Docker runs

#### Production Considerations
- **Resource Limits**: Memory and CPU constraints
- **Health Checks**: Monitoring container health
- **Secrets Management**: Secure API key handling
- **Multi-stage Builds**: Optimized image sizes

## 🛠️ Technical Implementation

### Environment Setup

#### Prerequisites
```bash
# Python 3.11+
python --version

# Docker and Docker Compose
docker --version
docker-compose --version

# Git
git --version
```

#### Development Environment
```bash
# Create project directory
mkdir agent-foundations
cd agent-foundations

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt

# Set up pre-commit hooks
pre-commit install
```

### Core Agent Implementation

#### Base Agent Class
The foundation of all agents follows a standard interface:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import asyncio
import logging

class BaseAgent(ABC):
    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = logging.getLogger(f"agent.{config.name}")
        self.memory = ShortTermMemory()
        self.tools = ToolRegistry()
        
    @abstractmethod
    async def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass
```

#### Research Agent Example
A specialized agent for research tasks:

```python
class ResearchAgent(BaseAgent):
    async def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # 1. Analyze task and break down
        research_plan = await self._create_research_plan(task)
        
        # 2. Execute research steps
        findings = []
        for step in research_plan.steps:
            result = await self._execute_research_step(step)
            findings.append(result)
            
        # 3. Synthesize results
        final_report = await self._synthesize_findings(findings)
        
        return {
            "task": task,
            "findings": findings,
            "report": final_report,
            "metadata": {
                "steps_executed": len(research_plan.steps),
                "sources_consulted": len([f for f in findings if f.get("sources")])
            }
        }
```

### Docker Configuration

#### Multi-stage Dockerfile
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create non-root user
RUN groupadd -r agent && useradd -r -g agent agent
RUN chown -R agent:agent /app
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
EXPOSE 8000
CMD ["python", "-m", "src.main"]
```

#### Docker Compose for Development
```yaml
version: '3.8'

services:
  agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - AGENT_ENV=development
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    depends_on:
      - redis
      - postgres
      
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
      
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: agents
      POSTGRES_USER: agent_user
      POSTGRES_PASSWORD: agent_pass
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  redis_data:
  postgres_data:
```

### Observability Implementation

#### Structured Logging
```python
import structlog

logger = structlog.get_logger()

# Context-aware logging
logger.info(
    "Task execution started",
    task_id=task_id,
    agent_name=self.config.name,
    user_id=context.get("user_id")
)
```

#### Metrics Collection
```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
TASK_COUNTER = Counter('agent_tasks_total', 'Total tasks processed', ['agent_name', 'status'])
TASK_DURATION = Histogram('agent_task_duration_seconds', 'Task execution time')
ACTIVE_TASKS = Gauge('agent_active_tasks', 'Currently active tasks')

# Use in agent
@TASK_DURATION.time()
async def execute_task(self, task: str):
    ACTIVE_TASKS.inc()
    try:
        result = await self._process_task(task)
        TASK_COUNTER.labels(agent_name=self.name, status='success').inc()
        return result
    except Exception as e:
        TASK_COUNTER.labels(agent_name=self.name, status='error').inc()
        raise
    finally:
        ACTIVE_TASKS.dec()
```

## 📋 Assignments & Exercises

### Exercise 1: Basic Agent Implementation
**Objective**: Build a simple agent that can answer questions using an LLM

**Requirements**:
- Implement `QuestionAnswerAgent` class
- Support different LLM providers (OpenAI, Anthropic)
- Add basic error handling and logging
- Include response time measurement

**Starter Code**: See `exercises/exercise_1_basic_agent.py`

**Success Criteria**:
- Agent responds to questions correctly
- Handles API errors gracefully
- Logs execution metrics
- Response time < 5 seconds

### Exercise 2: Tool Integration
**Objective**: Extend agent with tool-calling capabilities

**Requirements**:
- Implement function calling for web search
- Add calculator and weather tools
- Create tool registry system
- Handle tool execution errors

**Starter Code**: See `exercises/exercise_2_tool_integration.py`

**Success Criteria**:
- Agent can use multiple tools
- Tools are called appropriately for tasks
- Error handling for tool failures
- Tool usage is logged

### Exercise 3: Memory System
**Objective**: Add memory capabilities to maintain context

**Requirements**:
- Implement conversation memory
- Add semantic search over memories
- Create memory persistence
- Memory cleanup and optimization

**Starter Code**: See `exercises/exercise_3_memory_system.py`

**Success Criteria**:
- Agent remembers conversation history
- Can retrieve relevant past information
- Memory persists across sessions
- Memory usage is optimized

### Exercise 4: Containerized Deployment
**Objective**: Deploy agent in production-ready container

**Requirements**:
- Create optimized Dockerfile
- Set up health checks
- Configure logging and metrics
- Deploy with Docker Compose

**Starter Code**: See `production-configs/`

**Success Criteria**:
- Container builds successfully
- Health checks pass
- Metrics are exposed
- Logs are structured

## 🔧 Production Configuration

### API Server Setup
```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Agent API", version="1.0.0")

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

# Agent execution endpoint
@app.post("/execute")
async def execute_task(request: TaskRequest):
    try:
        result = await agent.execute(request.task, request.context)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Configuration Management
```python
from pydantic import BaseSettings

class AgentSettings(BaseSettings):
    # LLM Configuration
    openai_api_key: str
    model_name: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096
    
    # Database
    database_url: str = "postgresql://user:pass@localhost/agents"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = ".env"
```

### Security Implementation
```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException
import jwt

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/execute")
async def execute_task(request: TaskRequest, user=Depends(verify_token)):
    # Task execution with user context
    pass
```

## 📊 Evaluation Metrics

### Performance Metrics
- **Response Time**: Task completion time (target: < 5 seconds)
- **Throughput**: Tasks per minute (target: > 10)
- **Success Rate**: Successful task completions (target: > 95%)
- **Error Rate**: Failed executions (target: < 5%)

### Quality Metrics
- **Answer Accuracy**: Correctness of responses (manual evaluation)
- **Tool Usage**: Appropriate tool selection and usage
- **Context Retention**: Memory and conversation continuity
- **Code Quality**: Adherence to coding standards

### Operational Metrics
- **Container Health**: Successful health checks
- **Resource Usage**: CPU and memory consumption
- **Log Quality**: Structured and informative logging
- **Security**: Proper authentication and authorization

## 📚 Additional Resources

### Required Reading
- [LangChain Agent Documentation](https://docs.langchain.com/docs/components/agents/)
- [OpenAI Function Calling Guide](https://platform.openai.com/docs/guides/function-calling)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

### Recommended Papers
- "ReAct: Synergizing Reasoning and Acting in Language Models"
- "Toolformer: Language Models Can Teach Themselves to Use Tools"
- "Constitutional AI: Harmlessness from AI Feedback"

### Tools & Libraries
- **LLM Libraries**: LangChain, LlamaIndex, Semantic Kernel
- **API Frameworks**: FastAPI, Flask, Quart
- **Containerization**: Docker, Docker Compose
- **Monitoring**: Prometheus, Grafana, Jaeger

## 🎯 Week 1 Deliverables

1. **Research Agent Implementation**
   - Complete agent class with all features
   - Comprehensive test suite
   - Documentation and examples

2. **Containerized Deployment**
   - Production-ready Dockerfile
   - Docker Compose configuration
   - Health checks and monitoring

3. **API Server**
   - REST API with authentication
   - Request/response validation
   - Error handling and logging

4. **Performance Report**
   - Metrics collection and analysis
   - Performance benchmarks
   - Optimization recommendations

## 🚀 Next Week Preview

**Week 2: Advanced Reasoning & Cognitive Architectures**
- Implement Chain-of-Thought and Tree-of-Thoughts patterns
- Build cognitive architectures for complex reasoning
- Develop memory compression and summarization
- Create performance optimization frameworks

---

**Ready to build your first production agent? Let's get started!** 🤖