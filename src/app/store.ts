import type { Action, ThunkAction } from "@reduxjs/toolkit";
import { combineSlices, configureStore } from "@reduxjs/toolkit";
import { setupListeners } from "@reduxjs/toolkit/query";
import { authApi } from "../features/Login/LoginApi";
import { transactionsApi } from "../features/Transaction/TransactionApi";
import { regApi } from "../features/Register/RegApi";
import { LoginSlice } from "../features/Login/LoginSlice";
import { TransactionSlice } from "../features/Transaction/TransactionSlice";
import { NotificationSlice } from "../features/ui/Notification/NotificationSlice";
import { notificationsMiddleware } from "./notificationMiddleware";

const rootReducer = combineSlices(
  LoginSlice,
  TransactionSlice,
  NotificationSlice,
  {
    [authApi.reducerPath]: authApi.reducer,
  },
  {
    [transactionsApi.reducerPath]: transactionsApi.reducer,
  },
  {
    [regApi.reducerPath]: regApi.reducer,
  },
);

export type RootState = ReturnType<typeof rootReducer>;

export const makeStore = (preloadedState?: Partial<RootState>) => {
  const store = configureStore({
    reducer: rootReducer,
    middleware: getDefaultMiddleware => {
      return getDefaultMiddleware().concat(
        authApi.middleware,
        transactionsApi.middleware,
        regApi.middleware,
        notificationsMiddleware,
      );
    },
    preloadedState,
  });
  setupListeners(store.dispatch);
  return store;
};

export const store = makeStore();

export type AppStore = typeof store;
export type AppDispatch = AppStore["dispatch"];
export type AppThunk<ThunkReturnType = void> = ThunkAction<
  ThunkReturnType,
  RootState,
  unknown,
  Action
>;
