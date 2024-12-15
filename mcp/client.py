from typing import List, Optional, Dict, Any
import anthropic
from .mcp_core import (
    MCPRole,
    MCPMessageType,
    MCPContext,
    MCPMessage,
    MCPRequest,
    MCPResponse,
    MCPProtocol
)

class MCPClient:
    """Cliente MCP para interactuar con modelos de lenguaje."""
    
    def __init__(self, api_key: str):
        self.anthropic_client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-2.1"
        self.protocol = MCPProtocol()
    
    def _format_context(self, context_list: List[MCPContext]) -> str:
        """Formatea el contexto para el modelo."""
        return self.protocol.format_context(context_list)
    
    def _format_conversation_history(self, conversation_id: str) -> str:
        """Formatea el historial de la conversación."""
        conversation = self.protocol.get_conversation(conversation_id)
        if not conversation:
            return ""
            
        formatted = []
        for msg in conversation.messages:
            if msg.role == MCPRole.USER:
                formatted.append(f"{anthropic.HUMAN_PROMPT} {msg.content}")
            elif msg.role == MCPRole.ASSISTANT:
                formatted.append(f"{anthropic.ASSISTANT_PROMPT} {msg.content}")
            elif msg.role == MCPRole.SYSTEM:
                formatted.append(f"[System] {msg.content}")
        
        return "\n".join(formatted)
    
    async def generate_response(self, request: MCPRequest) -> MCPResponse:
        """Genera una respuesta usando el protocolo MCP."""
        try:
            # Obtener o crear conversación
            conversation = self.protocol.get_conversation(request.conversation_id)
            if not conversation:
                conversation = self.protocol.create_conversation(request.conversation_id)
            
            # Añadir mensaje del usuario
            self.protocol.add_message(request.conversation_id, request.message)
            
            # Preparar el prompt
            system_prompt = request.system_prompt or ""
            context = self._format_context(request.message.context or [])
            history = self._format_conversation_history(request.conversation_id)
            
            full_prompt = f"{system_prompt}\n\n{context}\n\n{history}"
            
            # Generar respuesta
            response = await self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=request.max_tokens or 1000,
                temperature=request.temperature,
                messages=[{
                    "role": "user",
                    "content": full_prompt
                }]
            )
            
            # Crear mensaje de respuesta
            message = MCPMessage(
                role=MCPRole.ASSISTANT,
                type=MCPMessageType.TEXT,
                content=response.content[0].text,
                metadata={"model": self.model}
            )
            
            # Crear respuesta MCP
            mcp_response = MCPResponse(
                conversation_id=request.conversation_id,
                message=message
            )
            
            # Añadir respuesta a la conversación
            self.protocol.add_message(request.conversation_id, message)
            
            return mcp_response
            
        except Exception as e:
            # Manejar error
            return self.protocol.handle_error(
                request.conversation_id,
                str(e),
                {"error_type": type(e).__name__}
            )
    
    def register_function(self, name: str, description: str, parameters: Dict[str, Any], required: List[str]):
        """Registra una función en el protocolo."""
        function = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "required": required
        }
        self.protocol.register_function(function)
    
    def update_conversation_state(self, conversation_id: str, updates: Dict[str, Any]):
        """Actualiza el estado de una conversación."""
        self.protocol.update_state(conversation_id, updates)
    
    def get_conversation_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el estado de una conversación."""
        conversation = self.protocol.get_conversation(conversation_id)
        return conversation.state if conversation else None 