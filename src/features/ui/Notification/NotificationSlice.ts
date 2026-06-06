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
        ...action.payload,
        status: "queued",
      });
    },
    showNotification: (state, action: PayloadAction<string>) => {
      const notification = state.notifications.find(
        n => n.id === action.payload,
      );
      if (notification && notification.status != "shown") {
        notification.status = "shown";
      }
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

export const {
  addNotification,
  removeNotification,
  resetNotification,
  showNotification,
} = NotificationSlice.actions;

const selectNotification = (state: RootState) => state.notifications;
export const selectNotifications = createSelector(
  selectNotification,
  notification => notification.notifications,
);
export const selectNotificationById = (id: string) =>
  createSelector(selectNotification, notification =>
    notification.notifications.find(n => n.id === id),
  );
