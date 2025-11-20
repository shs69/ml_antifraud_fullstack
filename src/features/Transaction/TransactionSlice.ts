import { createSelector } from "@reduxjs/toolkit";
import { createAppSlice } from "../../app/createAppSlice";
import type { RootState } from "../../app/store";
import type { TransactionState } from "../../interfaces";

const initialState: TransactionState = {
  createWindowOpen: false,
};

export const TransactionSlice = createAppSlice({
  name: "transaction",
  initialState: initialState,
  reducers: {
    openWindow: state => {
      state.createWindowOpen = true;
    },
    closeWindow: state => {
      state.createWindowOpen = false;
    },
  },
});

export const { openWindow, closeWindow } = TransactionSlice.actions;

const selectTransaction = (state: RootState) => state.transaction;
export const selectCreateWindowOpen = createSelector(
  selectTransaction,
  state => state.createWindowOpen,
);
