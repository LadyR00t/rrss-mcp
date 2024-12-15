from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class MCPRole(str, Enum):
    """Roles en el protocolo MCP."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"

class MCPMessageType(str, Enum):
    """Tipos de mensajes en el protocolo MCP."""
    TEXT = "text"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESULT = "function_result"
    ERROR = "error"
    STATE_UPDATE = "state_update"

class MCPContext(BaseModel):
    """Contexto del mensaje MCP."""
    source: str
    content: str
    metadata: Optional[Dict] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class MCPMessage(BaseModel):
    """Mensaje del protocolo MCP."""
    role: MCPRole
    type: MCPMessageType
    content: str
    context: Optional[List[MCPContext]] = None
    metadata: Optional[Dict] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class MCPConversation(BaseModel):
    """Conversación MCP."""
    id: str
    messages: List[MCPMessage] = Field(default_factory=list)
    state: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class MCPRequest(BaseModel):
    """Solicitud MCP."""
    conversation_id: str
    message: MCPMessage
    system_prompt: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    stream: bool = False

class MCPResponse(BaseModel):
    """Respuesta MCP."""
    conversation_id: str
    message: MCPMessage
    state_updates: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class MCPFunction(BaseModel):
    """Definición de función MCP."""
    name: str
    description: str
    parameters: Dict[str, Any]
    required: List[str]

class MCPProtocol:
    """Implementación del protocolo MCP."""
    
    def __init__(self):
        self.conversations: Dict[str, MCPConversation] = {}
        self.functions: Dict[str, MCPFunction] = {}
    
    def register_function(self, function: MCPFunction):
        """Registrar una función en el protocolo."""
        self.functions[function.name] = function
    
    def create_conversation(self, conversation_id: str) -> MCPConversation:
        """Crear una nueva conversación."""
        conversation = MCPConversation(id=conversation_id)
        self.conversations[conversation_id] = conversation
        return conversation
    
    def add_message(self, conversation_id: str, message: MCPMessage):
        """Añadir un mensaje a una conversación."""
        if conversation_id not in self.conversations:
            self.create_conversation(conversation_id)
        
        conversation = self.conversations[conversation_id]
        conversation.messages.append(message)
        conversation.updated_at = datetime.utcnow()
    
    def get_conversation(self, conversation_id: str) -> Optional[MCPConversation]:
        """Obtener una conversación por su ID."""
        return self.conversations.get(conversation_id)
    
    def update_state(self, conversation_id: str, updates: Dict[str, Any]):
        """Actualizar el estado de una conversación."""
        if conversation_id in self.conversations:
            conversation = self.conversations[conversation_id]
            conversation.state.update(updates)
            conversation.updated_at = datetime.utcnow()
    
    def validate_function_call(self, function_name: str, parameters: Dict[str, Any]) -> bool:
        """Validar una llamada a función."""
        if function_name not in self.functions:
            return False
            
        function = self.functions[function_name]
        required_params = set(function.required)
        provided_params = set(parameters.keys())
        
        return required_params.issubset(provided_params)
    
    def format_context(self, context_list: List[MCPContext]) -> str:
        """Formatear el contexto para su uso."""
        formatted = []
        for ctx in context_list:
            formatted.append(f"[{ctx.source}]\n{ctx.content}")
        return "\n\n".join(formatted)
    
    def create_response(
        self,
        conversation_id: str,
        content: str,
        message_type: MCPMessageType = MCPMessageType.TEXT,
        context: Optional[List[MCPContext]] = None,
        metadata: Optional[Dict] = None
    ) -> MCPResponse:
        """Crear una respuesta MCP."""
        message = MCPMessage(
            role=MCPRole.ASSISTANT,
            type=message_type,
            content=content,
            context=context,
            metadata=metadata
        )
        
        self.add_message(conversation_id, message)
        
        return MCPResponse(
            conversation_id=conversation_id,
            message=message,
            metadata=metadata
        )
    
    def handle_error(
        self,
        conversation_id: str,
        error_message: str,
        metadata: Optional[Dict] = None
    ) -> MCPResponse:
        """Manejar un error en el protocolo."""
        message = MCPMessage(
            role=MCPRole.SYSTEM,
            type=MCPMessageType.ERROR,
            content=error_message,
            metadata=metadata
        )
        
        self.add_message(conversation_id, message)
        
        return MCPResponse(
            conversation_id=conversation_id,
            message=message,
            metadata=metadata
        ) 