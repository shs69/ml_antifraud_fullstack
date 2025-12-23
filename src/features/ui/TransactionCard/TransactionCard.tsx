import type { JSX } from "react";
import "./TransactionCard.scss";
import type { TransactionCardProps } from "../../../interfaces";
import { getRightFormatTime } from "../../../utils/utils";

export const TransactionCard = (props: TransactionCardProps): JSX.Element => {
  const { date, time } = getRightFormatTime(props.data.created_at);
  return (
    <div
      className="transaction_card"
      style={{
        height: `${props.virtual_size.toString()}px`,
        transform: `translateY(${props.start.toString()}px)`,
      }}
    >
      <div className="shop_name">
        <span>{props.userTransactionCount - props.index}.</span>
        <span className="name">{props.data.shop_name}</span>
      </div>
      <div className="shop_address">{props.data.shop_adress}</div>
      <div className="created_at">
        <span>{date}</span>
        <span>{time}</span>
      </div>
      <div className="size">
        {props.data.is_refill ? "+" : "-"}
        {props.data.size}
      </div>
      <div className={props.data.fraud === "1" ? "fraud__error" : "fraud"}>
        {!props.data.fraud
          ? "pending"
          : props.data.fraud === "1"
            ? "Мошенническая"
            : "Обычная"}
      </div>
    </div>
  );
};
