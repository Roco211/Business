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

const COPY = {
  fallbackSessionTitle: "工作台会话",
  loadingTitle: "工作台加载中...",
  loadingDescription: "正在同步会话消息与确认任务。",
  workbenchTitle: "聊天工作台",
  sessionUnavailable: "会话不可用",
  messagesUnavailable: "消息加载失败",
  confirmationsUnavailable: "确认任务加载失败",
  resultsTitle: "处理结果",
  resultsSubtitle: "消息时间线与强化确认卡。",
  emptyTitle: "暂无工作台消息",
  emptyDescription: "可先使用引导入口，或直接发送文字。",
  composeTitle: "发送输入",
  composeSubtitle: "可用引导入口，或直接输入详细请求。",
  messageLabel: "消息",
  messagePlaceholder: "描述你的请求",
  sendFailed: "发送失败",
  sendAction: "发送更新",
  sendLoading: "发送中...",
  connectionConnected: "会话实时流已连接。",
  connectionConnecting: "正在尝试重连会话流。",
  connectionDegraded:
    "实时更新受限，执行操作后仍会触发手动刷新。",
  connectionIdle: "等待会话流启动。",
} as const;

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
    return COPY.connectionConnected;
  }
  if (connectionState === "connecting" || connectionState === "bootstrapping") {
    return COPY.connectionConnecting;
  }
  if (connectionState === "error" || connectionState === "disconnected") {
    return COPY.connectionDegraded;
  }
  return COPY.connectionIdle;
}

export default function ChatScreen() {
  const sessionStream = useSessionStream();
  const [draftText, setDraftText] = useState("");
  const sessionTitle =
    sessionStream.sessionTitle ?? sessionStream.sessionId ?? COPY.fallbackSessionTitle;
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
        <EmptyState title={COPY.loadingTitle} description={COPY.loadingDescription} />
      </AppScreen>
    );
  }

  const renderedConfirmationIds = new Set<string>();

  return (
    <AppScreen safeArea={false}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <WorkbenchHeader
          title={COPY.workbenchTitle}
          sessionTitle={sessionTitle}
          connectionState={sessionStream.connectionState}
          hint={getConnectionHint(sessionStream.connectionState)}
        />

        {sessionStream.bootstrapError ? (
          <InlineNotice
            tone="error"
            title={COPY.sessionUnavailable}
            message={sessionStream.bootstrapError}
          />
        ) : null}
        {messages.error ? (
          <InlineNotice tone="error" title={COPY.messagesUnavailable} message={messages.error} />
        ) : null}
        {confirmations.error ? (
          <InlineNotice
            tone="error"
            title={COPY.confirmationsUnavailable}
            message={confirmations.error}
          />
        ) : null}

        <SectionHeader title={COPY.resultsTitle} subtitle={COPY.resultsSubtitle} />
        {messages.data.length === 0 ? (
          <EmptyState title={COPY.emptyTitle} description={COPY.emptyDescription} />
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
            <SectionHeader title={COPY.composeTitle} subtitle={COPY.composeSubtitle} />
            <GuidedEntryDock sessionId={sessionStream.sessionId} onSubmitted={refreshChat} />
            <AppTextField
              label={COPY.messageLabel}
              placeholder={COPY.messagePlaceholder}
              value={draftText}
              onChangeText={setDraftText}
            />
            {sendMessage.error ? (
              <InlineNotice tone="error" title={COPY.sendFailed} message={sendMessage.error} />
            ) : null}
            <PrimaryButton
              label={COPY.sendAction}
              loading={sendMessage.isSubmitting}
              loadingLabel={COPY.sendLoading}
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
