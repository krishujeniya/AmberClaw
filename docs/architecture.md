# Architecture Deep-Dive

Message flow in AmberClaw is designed to be highly modular and clear:

1. **User Message**: Received from the chat platform interface.
2. **Channel**: Adapter parses it and extracts the intent.
3. **Bus**: Routes the message to the appropriate component.
4. **Agent**: Processes the intent and decides what actions to take.
5. **Tool**: Executes necessary actions based on the agent's decision.
6. **Memory**: Persists the context of the conversation.
7. **Response**: Formats and sends the output back to the user via the channel.

![Architecture](../assets/AmberClaw_arch.png)
