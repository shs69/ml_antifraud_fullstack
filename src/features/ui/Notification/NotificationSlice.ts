import { createAppSlice } from "../../../app/createAppSlice";
import { createSelector, type PayloadAction } from "@reduxjs/toolkit";
import { type Notification } from "../../../interfaces";
import { type RootState } from "../../../app/store";

const initialState: { notifications: Notification[] } = {
  notifications: [],
};

export const NotificationSlice = createAppSlice({
  name: "notifications",
  initialState: initialState,
  reducers: {
    addNotification: (state, action: PayloadAction<Notification>) => {
      state.notifications.push({
        id: action.payload.id,
        shop_name: action.payload.shop_name,
      });
    },
    removeNotification: (state, action: PayloadAction<string>) => {
      state.notifications = state.notifications.filter(
        notification => notification.id != action.payload,
      );
    },
    resetNotification: state => {
      state.notifications = [];
    },
  },
});

export const { addNotification, removeNotification, resetNotification } =
  NotificationSlice.actions;

const selectNotification = (state: RootState) => state.notifications;
export const selectNotifications = createSelector(
  selectNotification,
  notification => notification.notifications,
);
