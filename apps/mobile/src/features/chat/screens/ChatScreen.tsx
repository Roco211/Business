import { useState } from "react";
import { Button, ScrollView, Text, TextInput, View } from "react-native";

import { useSessionStream } from "../../../shared/session/useSessionStream";
import { useSendMessageMutation } from "../hooks/useSendMessageMutation";
import { useSessionMessagesQuery } from "../hooks/useSessionMessagesQuery";


function getActorLabel(actorType: string) {
  if (actorType === "owner") {
    return "Owner";
  }
  if (actorType === "system") {
    return "System";
  }
  return actorType;
}


function getMessageText(messageType: string, text: string | null) {
  if (text && text.trim().length > 0) {
    return text;
  }
  return `Unsupported ${messageType} message`;
}


export default function ChatScreen() {
  const sessionStream = useSessionStream();
  const [draftText, setDraftText] = useState("");
  const title = sessionStream.sessionTitle ?? sessionStream.sessionId ?? "工作群";
  const messages = useSessionMessagesQuery(sessionStream.sessionId);
  const sendMessage = useSendMessageMutation(sessionStream.sessionId);

  async function handleSend() {
    const result = await sendMessage.submitMessage(draftText);
    if (result === null) {
      return;
    }
    setDraftText("");
    messages.refresh();
  }

  if (messages.isLoading) {
    return (
      <View>
        <Text>Loading chat...</Text>
      </View>
    );
  }

  return (
    <ScrollView>
      <Text>{title}</Text>
      <Text>{sessionStream.connectionState}</Text>

      {sessionStream.bootstrapError ? (
        <View>
          <Text>Session unavailable</Text>
          <Text>{sessionStream.bootstrapError}</Text>
        </View>
      ) : null}

      {messages.error ? (
        <View>
          <Text>Chat unavailable</Text>
          <Text>{messages.error}</Text>
        </View>
      ) : null}

      <Text>Messages</Text>
      {messages.data.length === 0 ? <Text>No messages yet.</Text> : null}
      {messages.data.map((message) => (
        <View key={message.message_id}>
          <Text>{getActorLabel(message.actor_type)}</Text>
          <Text>{getMessageText(message.message_type, message.text)}</Text>
          <Text>{message.created_at}</Text>
        </View>
      ))}

      <Text>Composer</Text>
      <TextInput placeholder="Type a message" value={draftText} onChangeText={setDraftText} />
      {sendMessage.error ? <Text>{sendMessage.error}</Text> : null}
      <Button
        title={sendMessage.isSubmitting ? "Sending..." : "Send"}
        onPress={() => {
          void handleSend();
        }}
        disabled={sendMessage.isSubmitting}
      />
    </ScrollView>
  );
}
