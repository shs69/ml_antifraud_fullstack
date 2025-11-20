/* eslint-disable @typescript-eslint/no-invalid-void-type */
import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { formBody } from "../../utils/utils";
import type { RootState } from "../../app/store";
import type {
  LoginQueryArg,
  LoginResultToken,
  UserData,
} from "../../interfaces";

export const authApi = createApi({
  reducerPath: "authApi",
  baseQuery: fetchBaseQuery({
    baseUrl: "http://localhost:8000/login",
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).login.token;
      if (token) headers.set("Authorization", `Bearer ${token}`);
      return headers;
    },
  }),
  endpoints: build => ({
    login: build.mutation<LoginResultToken, LoginQueryArg>({
      query: credentials => ({
        url: "/access-token",
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formBody(credentials),
      }),
    }),
    getCurrentUser: build.query<UserData, void>({
      query: () => ({
        url: "/test-token",
        method: "POST",
      }),
    }),
    getCurrentUserById: build.query<UserData, string>({
      query: token => {
        const headers = new Headers();
        headers.append("Authorization", `Bearer ${token}`);

        return {
          url: "test-token",
          method: "POST",
          headers: headers,
        };
      },
    }),
  }),
});

export const {
  useLoginMutation,
  useGetCurrentUserQuery,
  useLazyGetCurrentUserQuery,
  useGetCurrentUserByIdQuery,
  useLazyGetCurrentUserByIdQuery,
} = authApi;
