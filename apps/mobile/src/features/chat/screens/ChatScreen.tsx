import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";

import { useSessionStream } from "../../../shared/session/useSessionStream";
import {
  AppScreen,
  AppTextField,
  DebugDisclosure,
  EmptyState,
  InlineNotice,
  PrimaryButton,
  SectionHeader,
  SurfaceCard,
  space,
} from "../../../shared/ui";
import { GuidedEntryDock } from "../components/GuidedEntryDock";
import { MessageResultCard } from "../components/MessageResultCard";
import { MockMediaEntryPanel } from "../components/MockMediaEntryPanel";
import { PendingReceiptConfirmationCard } from "../components/PendingReceiptConfirmationCard";
import { PendingStockInConfirmationCard } from "../components/PendingStockInConfirmationCard";
import { PendingStockOutConfirmationCard } from "../components/PendingStockOutConfirmationCard";
import { WorkbenchHeader } from "../components/WorkbenchHeader";
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

function getConnectionHint(connectionState: string) {
  if (connectionState === "connected") {
    return "Realtime session stream is active.";
  }
  if (connectionState === "connecting" || connectionState === "bootstrapping") {
    return "Attempting to reconnect to session stream.";
  }
  if (connectionState === "error" || connectionState === "disconnected") {
    return "Live updates are degraded. Manual refresh still applies after actions.";
  }
  return "Waiting for session stream.";
}

export default function ChatScreen() {
  const sessionStream = useSessionStream();
  const [draftText, setDraftText] = useState("");
  const sessionTitle = sessionStream.sessionTitle ?? sessionStream.sessionId ?? "Workbench session";
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

  useEffect(() => {
    if (sessionStream.dataResetVersion === 0) {
      return;
    }
    refreshChat();
  }, [sessionStream.dataResetVersion]);

  async function handleSend() {
    const result = await sendMessage.submitMessage(draftText);
    if (result === null) {
      return;
    }
    setDraftText("");
    refreshChat();
  }

  if (messages.isLoading && messages.data.length === 0) {
    return (
      <AppScreen safeArea={false}>
        <EmptyState
          title="Loading workbench..."
          description="Syncing session messages and confirmations."
        />
      </AppScreen>
    );
  }

  const renderedConfirmationIds = new Set<string>();

  return (
    <AppScreen safeArea={false}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <WorkbenchHeader
          title="Chat Workbench"
          sessionTitle={sessionTitle}
          connectionState={sessionStream.connectionState}
          hint={getConnectionHint(sessionStream.connectionState)}
        />

        {sessionStream.bootstrapError ? (
          <InlineNotice
            tone="error"
            title="Session unavailable"
            message={sessionStream.bootstrapError}
          />
        ) : null}
        {messages.error ? (
          <InlineNotice tone="error" title="Chat unavailable" message={messages.error} />
        ) : null}
        {confirmations.error ? (
          <InlineNotice
            tone="error"
            title="Confirmations unavailable"
            message={confirmations.error}
          />
        ) : null}

        <SectionHeader
          title="Results"
          subtitle="Message timeline and stronger confirmation checkpoints."
        />
        {messages.data.length === 0 ? (
          <EmptyState
            title="No workbench messages yet."
            description="Start with guided entry or send a text update."
          />
        ) : null}

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
            <View key={message.message_id} style={styles.timelineGroup}>
              <MessageResultCard
                messageId={message.message_id}
                actorLabel={getActorLabel(message.actor_type)}
                actorType={message.actor_type}
                messageType={message.message_type}
                text={getMessageText(message.message_type, message.text)}
                createdAt={message.created_at}
              />
              {linkedConfirmations.map((confirmation) => {
                if (confirmation.confirmation_type === "receipt-stock-in-batch") {
                  return (
                    <PendingReceiptConfirmationCard
                      key={confirmation.confirmation_id}
                      confirmation={confirmation}
                      onResolved={refreshChat}
                    />
                  );
                }
                if (confirmation.confirmation_type === "stock-out") {
                  return (
                    <PendingStockOutConfirmationCard
                      key={confirmation.confirmation_id}
                      confirmation={confirmation}
                      onResolved={refreshChat}
                    />
                  );
                }
                return (
                  <PendingStockInConfirmationCard
                    key={confirmation.confirmation_id}
                    confirmation={confirmation}
                    onResolved={refreshChat}
                  />
                );
              })}
            </View>
          );
        })}

        <SurfaceCard emphasis="elevated">
          <View style={styles.composer}>
            <SectionHeader
              title="Compose update"
              subtitle="Use guided entry or type details for the agent."
            />
            <GuidedEntryDock sessionId={sessionStream.sessionId} onSubmitted={refreshChat} />
            <AppTextField
              label="Message"
              placeholder="Describe your request"
              value={draftText}
              onChangeText={setDraftText}
            />
            {sendMessage.error ? (
              <InlineNotice tone="error" title="Message failed" message={sendMessage.error} />
            ) : null}
            <PrimaryButton
              label="Send update"
              loading={sendMessage.isSubmitting}
              loadingLabel="Sending..."
              onPress={() => {
                void handleSend();
              }}
              disabled={sendMessage.isSubmitting}
            />
            <DebugDisclosure title="Debug tools">
              <MockMediaEntryPanel sessionId={sessionStream.sessionId} onSubmitted={refreshChat} />
            </DebugDisclosure>
          </View>
        </SurfaceCard>
      </ScrollView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: space.s12,
    paddingBottom: space.s24,
  },
  timelineGroup: {
    gap: space.s8,
  },
  composer: {
    gap: space.s12,
  },
});
