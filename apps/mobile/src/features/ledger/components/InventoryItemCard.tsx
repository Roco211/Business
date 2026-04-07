import { StyleSheet, Text, View } from "react-native";

import type { InventoryItemRecord } from "../hooks/useInventoryItemsQuery";
import { PillActionButton, SurfaceCard } from "../../../shared/ui";
import { color, space } from "../../../shared/ui/tokens";

type InventoryItemCardProps = {
  item: InventoryItemRecord;
  onPressCorrection: () => void;
  onPressStockOut: () => void;
};

export function InventoryItemCard({ item, onPressCorrection, onPressStockOut }: InventoryItemCardProps) {
  return (
    <View testID={`inventory-card-${item.item_id}`}>
      <SurfaceCard emphasis="outlined">
        <View style={styles.header}>
          <Text style={styles.name}>{item.name}</Text>
          <Text style={styles.stock}>{`${item.current_stock} ${item.default_unit}`}</Text>
          <Text style={styles.price}>
            {item.current_price ? `单价 ${item.current_price}` : "单价待补充"}
          </Text>
        </View>
        <View style={styles.actions}>
          <PillActionButton
            label="库存修正"
            testID={`inventory-card-${item.item_id}-action-correction`}
            onPress={onPressCorrection}
          />
          <PillActionButton
            label="出库登记"
            testID={`inventory-card-${item.item_id}-action-stock-out`}
            onPress={onPressStockOut}
          />
        </View>
      </SurfaceCard>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    gap: space.s8,
  },
  name: {
    color: color.fgPrimary,
    fontSize: 18,
    fontWeight: "600",
  },
  stock: {
    color: color.fgPrimary,
    fontSize: 16,
  },
  price: {
    color: color.fgSecondary,
    fontSize: 14,
  },
  actions: {
    flexDirection: "row",
    gap: space.s8,
    marginTop: space.s12,
  },
});
