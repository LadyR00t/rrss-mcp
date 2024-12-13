from typing import List, Optional
import anthropic
from .models import Conversation, Message, MCPRequest

class AnthropicMCPClient:
    """Cliente MCP para Anthropic Claude."""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-2.1"  # Modelo por defecto
    
    def _format_messages(self, conversation: Conversation) -> str:
        """Formatea los mensajes para Claude."""
        formatted_messages = []
        for msg in conversation.messages:
            if msg.role == "user":
                formatted_messages.append(f"{anthropic.HUMAN_PROMPT} {msg.content}")
            elif msg.role == "assistant":
                formatted_messages.append(f"{anthropic.ASSISTANT_PROMPT} {msg.content}")
        return "".join(formatted_messages)
    
    def _format_context(self, conversation: Conversation) -> str:
        """Formatea el contexto para Claude."""
        if not conversation.context:
            return ""
        
        context_str = "\nContexto relevante:\n"
        for ctx in conversation.context:
            if ctx.source:
                context_str += f"[{ctx.source}]\n"
            context_str += f"{ctx.content}\n"
        return context_str
    
    async def generate_response(self, request: MCPRequest) -> Message:
        """Genera una respuesta usando Claude."""
        system_prompt = request.system_prompt or ""
        context = self._format_context(request.conversation)
        messages = self._format_messages(request.conversation)
        
        full_prompt = f"{system_prompt}{context}{messages}{anthropic.ASSISTANT_PROMPT}"
        
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=request.max_tokens or 1000,
            temperature=request.temperature,
            messages=[{
                "role": "user",
                "content": full_prompt
            }]
        )
        
        return Message(
            role="assistant",
            content=response.content[0].text,
            metadata={"model": self.model}
        ) 