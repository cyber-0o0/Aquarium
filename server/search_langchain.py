import langchain
import langchain_core
import langchain_openai
import langchain_anthropic

def find_class(class_name, modules):
    for module in modules:
        try:
            m = __import__(module, fromlist=[class_name])
            if hasattr(m, class_name):
                print(f"✅ Found {class_name} in {module}")
                return True
        except (ImportError, AttributeError):
            pass
    print(f"❌ Could not find {class_name} in any of {modules}")
    return False

modules_to_check = [
    "langchain.agents",
    "langchain.agents.agent",
    "langchain.agents.executor",
    "langchain_core.agents",
    "langchain_core.tools",
    "langchain.tools",
]

find_class("AgentExecutor", modules_to_check)
find_class("create_tool_calling_agent", modules_to_check)
find_class("StructuredTool", modules_to_check)
