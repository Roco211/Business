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
import { presentRuntimeMessageText } from "../utils/presentRuntimeMessageText";
import { getFriendlyStatusMessage } from "../../../shared/copy/getFriendlyStatusMessage";

const COPY = {
  fallbackSessionTitle: "工作台会话",
  loadingTitle: "正在同步工作台",
  loadingDescription: "请稍候，我们正在整理会话消息与待确认事项。",
  workbenchTitle: "门店助理",
  sessionUnavailable: "当前会话暂时不可用",
  messagesUnavailable: "消息列表暂时不可用",
  confirmationsUnavailable: "待确认事项暂时不可用",
  resultsTitle: "处理进展",
  resultsSubtitle: "消息、结果和待确认事项都会汇总在这里。",
  emptyTitle: "工作台里还没有新消息",
  emptyDescription: "可以先用引导入口，也可以直接发送文字请求。",
  composeTitle: "发消息给门店助理",
  composeSubtitle: "可以直接描述需求，也可以先选上面的常用入口。",
  messageLabel: "消息",
  messagePlaceholder: "输入今天想处理的事",
  sendFailed: "发送未完成",
  sendAction: "发送消息",
  sendLoading: "正在发送...",
  connectionConnected: "会话实时流已连接。",
  connectionConnecting: "正在尝试重连会话流。",
  connectionDegraded:
    "实时更新受限，执行操作后仍会触发手动刷新。",
  connectionIdle: "等待会话流启动。",
  actorOwner: "店主",
  actorSystem: "系统",
  actorFallback: "参与方",
  messageFallback: "此消息暂无可显示内容",
  debugTools: "调试工具",
} as const;

function getActorLabel(actorType: string) {
  if (actorType === "owner") {
    return COPY.actorOwner;
  }
  if (actorType === "system") {
    return COPY.actorSystem;
  }
  return COPY.actorFallback;
}

function getMessageText(actorType: string, actorId: string, text: string | null) {
  if (text && text.trim().length > 0) {
    const presentedText = presentRuntimeMessageText(text, {
      isRuntimeSystemMessage: actorType === "system" && actorId === "runtime",
    });
    if (presentedText.trim().length > 0) {
      return presentedText;
    }
  }
  return COPY.messageFallback;
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
            message={getFriendlyStatusMessage(sessionStream.bootstrapError, "请稍后再试。")}
          />
        ) : null}
        {messages.error ? (
          <InlineNotice
            tone="error"
            title={COPY.messagesUnavailable}
            message={getFriendlyStatusMessage(messages.error, "请稍后再试。")}
          />
        ) : null}
        {confirmations.error ? (
          <InlineNotice
            tone="error"
            title={COPY.confirmationsUnavailable}
            message={getFriendlyStatusMessage(confirmations.error, "请稍后再试。")}
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
                text={getMessageText(message.actor_type, message.actor_id, message.text)}
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
              <InlineNotice
                tone="error"
                title={COPY.sendFailed}
                message={getFriendlyStatusMessage(sendMessage.error, "请稍后再试。")}
              />
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
            <DebugDisclosure title={COPY.debugTools}>
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
