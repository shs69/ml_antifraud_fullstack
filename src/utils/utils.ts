import type { Dispatch, SetStateAction } from "react";
import type {
  CorrectTransactionBody,
  CreateTransactionBody,
} from "../interfaces";

export const formBody = (
  data: Record<string, string | number | boolean>,
): string =>
  Object.entries(data)
    .map(
      ([key, value]) =>
        `${encodeURIComponent(key)}=${encodeURIComponent(value)}`,
    )
    .join("&");

export const checkTokenLocalStorage = (): string | null => {
  return localStorage.getItem("token");
};

export const getRightFormatTime = (
  datetime: string,
): { time: string; date: string } => {
  const date = datetime.slice(0, 10).split("-").reverse().join(".");
  const rightTime = datetime.slice(11, 16);
  return { time: rightTime, date: date };
};

export const validateLogin = (
  email: string,
  password: string,
  setErrors: Dispatch<SetStateAction<{ email: string; password: string }>>,
): boolean => {
  const newErrors = {
    email: "",
    password: "",
  };

  if (!email.trim()) newErrors.email = "Электронная почта";
  if (!password.trim()) newErrors.password = "Пароль";

  setErrors(newErrors);
  return Object.values(newErrors).every(e => e === "");
};

export const validateReg = (
  email: string,
  password: string,
  homeAddress: string,
  fullName: string,
  setErrors: Dispatch<
    SetStateAction<{
      email: string;
      password: string;
      homeAddress: string;
      fullName: string;
    }>
  >,
): boolean => {
  const newErrors = {
    email: "",
    password: "",
    homeAddress: "",
    fullName: "",
  };

  if (!email.trim()) newErrors.email = "Электронная почта";
  if (!password.trim()) newErrors.password = "Пароль";
  if (!homeAddress.trim()) newErrors.homeAddress = "Домашний адрес";
  if (!fullName.trim()) newErrors.fullName = "ФИО";

  setErrors(newErrors);
  return Object.values(newErrors).every(e => e === "");
};

export const validateNewTransaction = (
  shopName: string,
  shopAddress: string,
  size: string,
  setErrors: Dispatch<
    SetStateAction<{
      shopName: string;
      shopAddress: string;
      size: string;
    }>
  >,
): boolean => {
  const newErrors = {
    shopName: "",
    shopAddress: "",
    size: "",
  };

  if (!shopName.trim()) newErrors.shopName = "Введите название магазина";
  if (!shopAddress.trim()) newErrors.shopAddress = "Введите адрес магазина";
  if (!size || parseInt(size) <= 0) newErrors.size = "Введите сумму";

  setErrors(newErrors);
  return Object.values(newErrors).every(e => e === "");
};

export const getRightNewTransaction = (
  oldData: CreateTransactionBody,
): CorrectTransactionBody => {
  const isRefill = oldData.isRefill === "refill" ? true : false;
  const onlineOrder = oldData.paymentMethod === "online" ? true : false;
  const usedPin = oldData.paymentMethod === "pin" ? true : false;
  const usedChip =
    oldData.paymentMethod === "card" ? true : usedPin ? true : false;
  return {
    shop_name: oldData.shopName,
    shop_adress: oldData.shopAddress,
    is_refill: isRefill,
    size: oldData.size,
    used_chip: usedChip,
    used_pin_number: usedPin,
    online_order: onlineOrder,
  };
};
