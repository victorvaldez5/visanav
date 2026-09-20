<template>
  <form
    class="grow mx-auto w-3/5 lg:w-2/5 h-screen flex flex-col justify-center gap-4"
    @submit.prevent="onSubmit"
  >
    <h3 class="mb-4 text-center text-2xl font-medium text-foreground tracking-tight">
      Register
    </h3>
    <FormField
      v-slot="{ componentField }"
      v-model="values.email"
      name="email"
      validate-on-change
      validate-on-blur
    >
      <FormItem>
        <FormLabel>Email</FormLabel>
        <FormControl>
          <Input
            type="email"
            v-bind="componentField"
          />
        </FormControl>
        <FormMessage />
      </FormItem>
    </FormField>

    <FormField
      v-slot="{ componentField }"
      v-model="values.password"
      name="password"
      validate-on-change
      validate-on-blur
    >
      <FormItem>
        <FormLabel>Password</FormLabel>
        <FormControl>
          <Input
            type="password"
            v-bind="componentField"
          />
        </FormControl>
        <FormMessage />
      </FormItem>
    </FormField>

    <FormField
      v-slot="{ componentField }"
      v-model="values.password2"
      name="password2"
      validate-on-change
      validate-on-blur
    >
      <FormItem>
        <FormLabel>Verify Password</FormLabel>
        <FormControl>
          <Input
            type="password"
            v-bind="componentField"
          />
        </FormControl>
        <FormMessage />
      </FormItem>
    </FormField>

    <div
      ref="turnstileEl"
      class="flex justify-center"
    />

    <Button :disabled="loading">
      {{ loading ? "Creating Account..." : "Create Account" }}
    </Button>
  </form>
</template>

<script setup lang="ts">
import {useTemplateRef} from "vue";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {useAuthStore} from "@/stores/useAuthStore.ts";
import {storeToRefs} from "pinia";
import {toTypedSchema} from "@vee-validate/zod";
import {z} from "zod";
import {useForm} from "vee-validate";
import {FormControl, FormField, FormItem, FormLabel, FormMessage} from "@/components/ui/form";
import {useTurnstile} from "@/composables/useTurnstile";

interface RegisterForm {
  email: string;
  password: string;
  password2: string | null;
}

const authStore = useAuthStore();
const {loading, error} = storeToRefs(authStore);
const {register} = authStore;

const formSchema = toTypedSchema(z.object({
  email: z.string().email().nonempty(),
  password: z.string().min(8),
  password2: z.string().min(8),
}).refine((data) => data.password === data.password2, {
  message: "Passwords do not match",
  path: ["password2"],
}));

const {values, handleSubmit, setErrors} = useForm<RegisterForm>({
  validationSchema: formSchema,
});

const turnstileEl = useTemplateRef<HTMLElement>("turnstileEl");
const {token: turnstileToken, reset: resetTurnstile} = useTurnstile(turnstileEl);

const onSubmit = handleSubmit(async (submitValues) => {
  try {
    if (submitValues.password !== submitValues.password2) {
      error.value = "Passwords do not match";
      return
    }
    await register(submitValues.email, submitValues.password, submitValues.password2, turnstileToken.value);
  } catch (e: any) {
    resetTurnstile(); // token is single-use; refresh it for a retry
    console.error(e.response?.data);
    setErrors({
      email: e.response?.data?.email,
      password: e.response?.data?.password
    });
  }
});
</script>
