export type LoginType = {
  token: string | null;
  user: {
    email: string;
    full_name: string;
    home_address: string;
    balance: string;
  } | null;
  authLoading: boolean;
};

export type TransactionState = {
  createWindowOpen: boolean;
};

export type SetAuthDataPayload = {
  user: UserData;
  token: string;
  authLoading: boolean;
};

export type UserData = {
  email: string;
  full_name: string;
  home_adress: string;
  balance: string;
};

export type LoginQueryArg = {
  username: string;
  password: string;
};

export type LoginResultToken = {
  access_token: string;
  token_type: string;
};

export type CreateTransactionBody = {
  shopName: string;
  shopAddress: string;
  isRefill: "refill" | "withdraw";
  size: number;
  paymentMethod: "online" | "card" | "pin";
};

export type Transaction = {
  shop_name: string;
  shop_adress: string;
  is_refill: boolean;
  size: number;
  used_chip: boolean;
  used_pin_number: boolean;
  online_order: boolean;
  id: string;
  created_at: string;
  fraud: string | null;
};

export type Transactions = {
  count: number;
  data: Transaction[];
};

export type CorrectTransactionBody = {
  shop_name: string;
  shop_adress: string;
  is_refill: boolean;
  size: number;
  used_chip: boolean;
  used_pin_number: boolean;
  online_order: boolean;
};

export type RegisterResult = {
  email: string;
  full_name: string;
  is_active: boolean;
  home_adress: string;
  balance: number;
  id: string;
};

export type RegisterBody = {
  email: string;
  password: string;
  fullName: string;
  homeAddress: string;
};

export type TransactionCardProps = {
  userTransactionCount: number;
  start: number;
  virtual_size: number;
  index: number;
  data: {
    created_at: string;
    id: string;
    shop_name: string;
    shop_adress: string;
    size: number;
    is_refill: boolean;
    online_order: boolean;
    used_chip: boolean;
    used_pin_number: boolean;
    fraud: string | null;
  };
};

export type FirstCardProps = {
  shop_name: string;
  shop_address: string;
  created_at: string;
  size: string;
  fraud: string;
};

export type RowProps = {
  children?: React.ReactNode;
};

export type RowElemProps = {
  name: string;
  value: string;
  fontSize?: string;
  cursor?: string;
};
