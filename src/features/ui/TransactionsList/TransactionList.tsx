import { TransactionCard } from "../TransactionCard/TransactionCard";
import { useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useGetTransactionsQuery } from "../../Transaction/TransactionApi";
import { selectUser } from "../../Login/LoginSlice";
import type { JSX } from "react";
import "./TransactionList.scss";
import { useAppSelector } from "../../../app/hooks";

export const TransactionList = ({
  userTransactionsCount,
}: {
  userTransactionsCount: number;
}): JSX.Element => {
  const user = useAppSelector(selectUser);
  const parentRef = useRef<HTMLDivElement>(null);
  const [limit, setLimit] = useState(50);
  const { data, isFetching } = useGetTransactionsQuery(
    {
      offset: 0,
      limit: limit,
    },
    { skip: !user },
  );

  const count = data ? data.data.length : 0;
  const transactions = data ? data.data : [];
  const isAllTransactionsLoaded = userTransactionsCount === count;

  const rowVirtualizer = useVirtualizer({
    count: count,
    estimateSize: () => 40,
    getScrollElement: () => parentRef.current,
    overscan: 5,
  });

  const items = rowVirtualizer.getVirtualItems();

  if (!isFetching && items.length) {
    const last = items[items.length - 1];

    const isNearBottom = last.index >= transactions.length - 5;

    if (isNearBottom && !isAllTransactionsLoaded) {
      setLimit(prev => prev + 50);
    }
  }

  return (
    <div ref={parentRef} className="transaction_list">
      <div
        className="transaction_card"
        style={{ position: "relative", marginBottom: "0", paddingBottom: "0" }}
      >
        <div className="shop_name">
          <span>Название</span>
        </div>
        <div className="shop_address">Адрес</div>
        <div className="created_at">
          <span>Время</span>
        </div>
        <div className="size">Сумма</div>
        <div className="fraud">Статус</div>
      </div>
      <div
        className="transaction_list__transactions"
        style={{
          height: `${rowVirtualizer.getTotalSize().toString()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {rowVirtualizer.getVirtualItems().map(virtualRow => (
          <TransactionCard
            key={virtualRow.index}
            index={virtualRow.index}
            virtual_size={virtualRow.size}
            start={virtualRow.start}
            data={transactions[virtualRow.index]}
            userTransactionCount={userTransactionsCount}
          />
        ))}
      </div>
    </div>
  );
};
