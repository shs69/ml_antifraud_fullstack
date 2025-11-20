import { createAppSlice } from "../../app/createAppSlice";
import type { LoginType, SetAuthDataPayload, UserData } from "../../interfaces";
import type { RootState } from "../../app/store";
import { createSelector, type PayloadAction } from "@reduxjs/toolkit";

const initialState: LoginType = {
  token: null,
  user: null,
};

export const LoginSlice = createAppSlice({
  name: "login",
  initialState: initialState,
  reducers: {
    logout: state => {
      state.token = null;
      state.user = null;
      localStorage.removeItem("token");
    },
    setToken: (state, action: PayloadAction<string>) => {
      state.token = action.payload;
    },
    setUser: (state, action: PayloadAction<UserData>) => {
      state.user = {
        full_name: action.payload.full_name,
        email: action.payload.email,
        home_address: action.payload.home_adress,
        balance: action.payload.balance,
      };
    },
    setAuthData: (state, action: PayloadAction<SetAuthDataPayload>) => {
      state.user = {
        full_name: action.payload.user.full_name,
        email: action.payload.user.email,
        home_address: action.payload.user.home_adress,
        balance: action.payload.user.balance,
      };
      state.token = action.payload.token;
    },
  },
});

export const { logout, setToken, setUser, setAuthData } = LoginSlice.actions;

export const selectAuth = (state: RootState) => state.login;
export const selectToken = createSelector(selectAuth, auth => auth.token);
export const selectUser = createSelector(selectAuth, auth => auth.user);
