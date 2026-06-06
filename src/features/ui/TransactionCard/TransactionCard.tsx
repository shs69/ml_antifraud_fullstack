import type { JSX } from "react";
import "./TransactionCard.scss";
import type { TransactionCardProps } from "../../../interfaces";
import { getRightFormatTime } from "../../../utils/utils";
import { useAppDispatch } from "../../../app/hooks.ts";
import { openDetails } from "../../Transaction/TransactionSlice.ts";

export const TransactionCard = (props: TransactionCardProps): JSX.Element => {
  const dispatch = useAppDispatch();

  const openDetailsFn = () => {
    dispatch(openDetails(props.data));
  };

  const { date, time } = getRightFormatTime(props.data.created_at);
  return (
    <div
      className="transaction_card"
      style={{
        height: `${props.virtual_size.toString()}px`,
        transform: `translateY(${props.start.toString()}px)`,
        cursor: "pointer",
      }}
      onClick={openDetailsFn}
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
