import { useEffect, useState } from "react";
import { Button, ScrollView, Text, TextInput, View } from "react-native";

import { useSessionStream } from "../../../shared/session/useSessionStream";
import { PendingStockInConfirmationCard } from "../components/PendingStockInConfirmationCard";
import { useChatPendingConfirmationsQuery } from "../hooks/useChatPendingConfirmationsQuery";
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
  const confirmations = useChatPendingConfirmationsQuery(sessionStream.sessionId);
  const sendMessage = useSendMessageMutation(sessionStream.sessionId);

  function refreshChat() {
    messages.refresh();
    confirmations.refresh();
  }

  useEffect(() => {
    const eventType = sessionStream.lastEvent?.event_type;
    if (
      eventType !== "message.created"
      && eventType !== "task.updated"
      && eventType !== "confirmation.created"
      && eventType !== "confirmation.resolved"
      && eventType !== "inventory.updated"
    ) {
      return;
    }
    refreshChat();
  }, [sessionStream.lastEvent?.event_id]);

  async function handleSend() {
    const result = await sendMessage.submitMessage(draftText);
    if (result === null) {
      return;
    }
    setDraftText("");
    refreshChat();
  }

  if (messages.isLoading) {
    return (
      <View>
        <Text>Loading chat...</Text>
      </View>
    );
  }

  const renderedConfirmationIds = new Set<string>();

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

      {confirmations.error ? (
        <View>
          <Text>Confirmations unavailable</Text>
          <Text>{confirmations.error}</Text>
        </View>
      ) : null}

      <Text>Messages</Text>
      {messages.data.length === 0 ? <Text>No messages yet.</Text> : null}
      {messages.data.map((message) => {
        const linkedConfirmations = confirmations.data.filter((confirmation) => {
          if (confirmation.task_run_id !== message.task_run_id) {
            return false;
          }
          if (renderedConfirmationIds.has(confirmation.confirmation_id)) {
            return false;
          }
          renderedConfirmationIds.add(confirmation.confirmation_id);
          return true;
        });

        return (
          <View key={message.message_id}>
            <View>
              <Text>{getActorLabel(message.actor_type)}</Text>
              <Text>{getMessageText(message.message_type, message.text)}</Text>
              <Text>{message.created_at}</Text>
            </View>
            {linkedConfirmations.map((confirmation) => (
              <PendingStockInConfirmationCard
                key={confirmation.confirmation_id}
                confirmation={confirmation}
                onResolved={refreshChat}
              />
            ))}
          </View>
        );
      })}

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
