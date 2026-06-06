import { forwardRef, type JSX } from "react";
import { useAppDispatch, useAppSelector } from "../../../app/hooks.ts";
import { closeDetails, selectDetailsTransaction } from "../TransactionSlice.ts";
import "./TransactionWindow.scss";
import { RowBtn } from "../../ui/RowElementBtn/RowBtn.tsx";
import { Row } from "../../ui/HomeRow/Row.tsx";

export const TransactionWindow = forwardRef<HTMLDivElement>(
  (_, ref): JSX.Element => {
    const dispatch = useAppDispatch();
    const detailsTransaction = useAppSelector(selectDetailsTransaction);
    const rawReasons = (detailsTransaction?.reasons ?? "").replace(/'/g, '"');

    const closeWindowFn = () => {
      dispatch(closeDetails());
    };

    return (
      <div className="blur_foreground">
        <div className="window" ref={ref}>
          <div className="shop_name">{detailsTransaction?.shop_name ?? ""}</div>
          <div className="cont">
            <div className="shop_address">
              Адрес: {detailsTransaction?.shop_adress ?? ""}
            </div>
            <div
              className={
                detailsTransaction?.fraud === "1" ? "fraud__error" : "fraud"
              }
            >
              Статус операции:{" "}
              {!detailsTransaction?.fraud
                ? "pending"
                : detailsTransaction.fraud === "1"
                  ? "Мошенническая"
                  : "Обычная"}
            </div>
            {detailsTransaction?.fraud === "1" &&
              <div className="reasons">
                Причины:
                {(JSON.parse(rawReasons) as string[]).map((elem, i) => (
                  <div key={i} className="reason">
                    {i + 1}. {elem}
                  </div>
                ))}
              </div>
            }
          </div>
          <Row>
            <RowBtn
              value="Назад"
              onClick={closeWindowFn}
              style={{ alignItems: "center" }}
            />
          </Row>
        </div>
      </div>
    );
  },
);
