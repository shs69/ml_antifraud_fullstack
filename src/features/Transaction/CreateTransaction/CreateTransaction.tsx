import type { JSX } from "react";
import "./CreateTransaction.scss";
import { Row } from "../../ui/HomeRow/Row";
import { RowBtn } from "../../ui/RowElementBtn/RowBtn";
import { closeWindow } from "../TransactionSlice";
import { useAppDispatch } from "../../../app/hooks";
import { forwardRef, useState } from "react";
import { validateNewTransaction } from "../../../utils/utils";
import type { FetchBaseQueryError } from "@reduxjs/toolkit/query/react";
import {
  useCreateTransactionMutation,
  useUploadFileMutation,
} from "../TransactionApi";

export const CreateTransaction = forwardRef<HTMLDivElement>(
  (_, ref): JSX.Element => {
    const [shopName, setShopName] = useState("");
    const [shopAddress, setShopAddress] = useState("");
    const [isRefill, setRefill] = useState<"refill" | "withdraw">("withdraw");
    const [size, setSize] = useState("1");
    const [paymentMethod, setPaymentMethod] = useState<
      "online" | "card" | "pin"
    >("online");
    const [file, setFile] = useState<File | null>(null);
    const dispatch = useAppDispatch();
    const [createTransaction] = useCreateTransactionMutation();
    const [uploadFile] = useUploadFileMutation();

    const [errors, setErrors] = useState({
      shopName: "",
      shopAddress: "",
      size: "",
    });

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files?.[0];
      if (!selected) return false;

      setFile(selected);
    };

    const createTransactionFn = async () => {
      if (file) {
        try {
          await uploadFile(file);
          closeWindowFn();
        } catch (err) {
          const error = err as FetchBaseQueryError;
          console.log("Ошибка:", error.data ?? error);
        }
        return;
      }

      if (!validateNewTransaction(shopName, shopAddress, size, setErrors)) {
        setTimeout(() => {
          setErrors({
            shopName: "",
            shopAddress: "",
            size: "",
          });
        }, 400);
        return;
      }

      const newTransactionData = {
        shopName: shopName,
        shopAddress: shopAddress,
        isRefill: isRefill,
        size: parseInt(size),
        paymentMethod: paymentMethod,
      };

      try {
        await createTransaction(newTransactionData).unwrap();
        closeWindowFn();
      } catch (err) {
        const error = err as FetchBaseQueryError;
        console.log("Ошибка:", error.data ?? error);
      }
    };

    const closeWindowFn = () => {
      dispatch(closeWindow());
    };

    return (
      <div className="blur_foreground">
        <div className="create_transaction_window" ref={ref}>
          <h1>Новая транзакция</h1>
          <form>
            <label>
              <div
                className={
                  errors.shopName ? "error" : "create_transaction_window__text"
                }
              >
                Введите имя магазина
              </div>
              <input
                name="shopName"
                type="text"
                id="shopName"
                value={shopName}
                onChange={e => {
                  setShopName(e.target.value);
                }}
              />
            </label>
            <label>
              <div
                className={
                  errors.shopAddress
                    ? "error"
                    : "create_transaction_window__text"
                }
              >
                Введите адрес магазина
              </div>
              <input
                name="shopAddress"
                type="text"
                id="shopAddress"
                value={shopAddress}
                onChange={e => {
                  setShopAddress(e.target.value);
                }}
              />
            </label>
            <label>
              Выберите тип операции
              <select
                value={isRefill}
                onChange={e => {
                  setRefill(
                    e.target.value === "refill" ? "refill" : "withdraw",
                  );
                }}
              >
                <option value="withdraw">Списание</option>
                <option value="refill">Пополнение</option>
              </select>
            </label>
            <label>
              <div
                className={
                  errors.size ? "error" : "create_transaction_window__text"
                }
              >
                Введите сумму операции
              </div>
              <input
                name="size"
                type="number"
                id="size"
                value={size}
                onChange={e => {
                  setSize(e.target.value);
                }}
              />
            </label>
            <label>
              Выберите способ оплаты
              <select
                value={paymentMethod}
                onChange={e => {
                  setPaymentMethod(e.target.value as "online" | "card" | "pin");
                }}
              >
                <option value="online">Онлайн заказ</option>
                <option value="card">Картой</option>
                <option value="pin">Картой с примением пин-кода</option>
              </select>
            </label>
            <div className="loadFile">
              или загрузите CSV файл
              <label>
                {!file ? "Загрузить файл" : file.name}
                <input
                  className="inputFile"
                  name="loadFile"
                  type="file"
                  id="loadFile"
                  accept=".csv,text/csv"
                  onChange={handleFileChange}
                />
              </label>
            </div>
          </form>
          <Row>
            <RowBtn
              value="Отмена"
              onClick={closeWindowFn}
              style={{ alignItems: "center" }}
            />
            <RowBtn
              value="Создать"
              onClick={() => void createTransactionFn()}
              style={{
                alignItems: "center",
                backgroundColor: "rgb(100, 166, 240, 1)",
                color: "white",
                outline: "0.15rem solid white",
                outlineOffset: "-0.3rem",
              }}
            />
          </Row>
        </div>
      </div>
    );
  },
);
