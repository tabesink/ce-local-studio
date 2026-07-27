"use client";

import { ListRow } from "@/_shared/ui";

/** Settings-owned row composition over residual ListRow (P9-01 U3 / KTD5). */
export function SettingsRow(props: Parameters<typeof ListRow>[0]) {
  return <ListRow {...props} />;
}
