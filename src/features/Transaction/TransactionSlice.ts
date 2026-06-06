import { createSelector, type PayloadAction } from "@reduxjs/toolkit";
import { createAppSlice } from "../../app/createAppSlice";
import type { RootState } from "../../app/store";
import type { TransactionState } from "../../interfaces";

const initialState: TransactionState = {
  createWindowOpen: false,
  detailsWindowsOpen: false,
  detailsTransaction: null,
};

export const TransactionSlice = createAppSlice({
  name: "transaction",
  initialState: initialState,
  reducers: {
    openDetails: (
      state,
      action: PayloadAction<TransactionState["detailsTransaction"]>,
    ) => {
      state.detailsWindowsOpen = true;
      state.detailsTransaction = null;
      state.detailsTransaction = action.payload;
    },
    closeDetails: state => {
      state.detailsWindowsOpen = false;
    },
    openWindow: state => {
      state.createWindowOpen = true;
    },
    closeWindow: state => {
      state.createWindowOpen = false;
    },
  },
});

export const { openWindow, closeWindow, openDetails, closeDetails } =
  TransactionSlice.actions;

const selectTransaction = (state: RootState) => state.transaction;
export const selectCreateWindowOpen = createSelector(
  selectTransaction,
  state => state.createWindowOpen,
);
export const selectDetailsWindowOpen = createSelector(
  selectTransaction,
  state => state.detailsWindowsOpen,
);
export const selectDetailsTransaction = createSelector(
  selectTransaction,
  state => state.detailsTransaction,
);
