import { StyleSheet, Text, View } from "react-native";

import { EmptyState, SectionHeader, StatusBadge, SurfaceCard, color, radius, space } from "../../../shared/ui";

type ExceptionTone = "warning" | "error" | "success" | "neutral";

export type DashboardExceptionItem = {
  id: string;
  title: string;
  detail: string;
  badgeTone?: ExceptionTone;
  badgeLabel?: string;
};

type DashboardExceptionCardProps = {
  title: string;
  subtitle: string;
  emptyTitle: string;
  emptyDescription: string;
  items: DashboardExceptionItem[];
};

export function DashboardExceptionCard({
  title,
  subtitle,
  emptyTitle,
  emptyDescription,
  items,
}: DashboardExceptionCardProps) {
  return (
    <SurfaceCard emphasis="outlined">
      <SectionHeader title={title} subtitle={subtitle} />
      {items.length === 0 ? (
        <EmptyState title={emptyTitle} description={emptyDescription} />
      ) : (
        <View style={styles.list}>
          {items.map((item) => (
            <View key={item.id} style={styles.item}>
              <View style={styles.itemHeading}>
                <Text style={styles.itemTitle}>{item.title}</Text>
                {item.badgeLabel ? (
                  <StatusBadge tone={item.badgeTone ?? "neutral"} label={item.badgeLabel} />
                ) : null}
              </View>
              <Text style={styles.itemDetail}>{item.detail}</Text>
            </View>
          ))}
        </View>
      )}
    </SurfaceCard>
  );
}

const styles = StyleSheet.create({
  list: {
    gap: space.s10,
    marginTop: space.s12,
  },
  item: {
    backgroundColor: "rgba(255, 255, 255, 0.76)",
    borderColor: "rgba(45, 33, 28, 0.06)",
    borderRadius: radius.card,
    borderWidth: 1,
    gap: space.s8,
    padding: space.s12,
  },
  itemHeading: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  itemTitle: {
    color: color.fgPrimary,
    flex: 1,
    fontSize: 15,
    fontWeight: "600",
    paddingRight: space.s8,
  },
  itemDetail: {
    color: color.fgSecondary,
    fontSize: 14,
    lineHeight: 20,
  },
});
